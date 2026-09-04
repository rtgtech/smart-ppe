"""Real-time YOLO PPE detection and local face identification services."""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from ultralytics import YOLO

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import SafetyScore, Worker
from app.services.face_recognition import (
    FaceEngine,
    FaceRegistry,
    FaceServiceError,
    annotate_faces,
    validate_person_id,
)
from app.services.ppe_compliance import (
    MODEL_PPE_CLASSES,
    PPE_ITEM_SPECS,
    PersonTracker,
    analyze_compliance,
    annotate_compliance,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
STREAM_SERVER_DIR = REPOSITORY_ROOT / "stream_test" / "server"

MODEL_PATH = Path(
    os.getenv("YOLO_MODEL_PATH", str(REPOSITORY_ROOT / "best2.pt"))
).expanduser().resolve()
POSE_MODEL_SPEC = os.getenv("YOLO_POSE_MODEL", "yolo11n-pose.pt").strip() or "yolo11n-pose.pt"
FACE_DETECTOR_PATH = Path(
    os.getenv(
        "FACE_DETECTOR_PATH",
        str(STREAM_SERVER_DIR / "models" / "face_detection_yunet_2023mar.onnx"),
    )
).expanduser().resolve()
FACE_RECOGNIZER_PATH = Path(
    os.getenv(
        "FACE_RECOGNIZER_PATH",
        str(STREAM_SERVER_DIR / "models" / "face_recognition_sface_2021dec.onnx"),
    )
).expanduser().resolve()
FACE_REGISTRY_PATH = Path(
    os.getenv("FACE_REGISTRY_PATH", str(STREAM_SERVER_DIR / "data" / "faces.json"))
).expanduser().resolve()

DEVICE = os.getenv("YOLO_DEVICE", "").strip() or None
IMAGE_SIZE = int(os.getenv("YOLO_IMAGE_SIZE", "640"))
MAX_FRAME_BYTES = int(os.getenv("MAX_FRAME_BYTES", "5000000"))
FACE_SIMILARITY_THRESHOLD = float(os.getenv("FACE_SIMILARITY_THRESHOLD", "0.363"))
POSE_CONFIDENCE = float(os.getenv("YOLO_POSE_CONFIDENCE", "0.35"))
PPE_REGION_OVERLAP = float(os.getenv("PPE_REGION_OVERLAP", "0.50"))
settings = get_settings()

router = APIRouter(tags=["vision"])
vision_lock = asyncio.Lock()
yolo_model: YOLO | None = None
pose_model: YOLO | None = None
face_engine: FaceEngine | None = None
face_registry: FaceRegistry | None = None


def _load_services() -> tuple[YOLO, YOLO, FaceEngine, FaceRegistry]:
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"YOLO weights not found at '{MODEL_PATH}'. Set YOLO_MODEL_PATH to a local .pt file."
        )
    model = YOLO(str(MODEL_PATH))
    available = {str(name).lower() for name in model.names.values()}
    missing = sorted(MODEL_PPE_CLASSES - available)
    if missing:
        raise RuntimeError(f"The YOLO model is missing required gate classes: {', '.join(missing)}")
    pose = YOLO(POSE_MODEL_SPEC)
    if pose.task != "pose":
        raise RuntimeError(f"The configured pose model '{POSE_MODEL_SPEC}' is not a YOLO pose checkpoint.")
    engine = FaceEngine(
        detector_path=FACE_DETECTOR_PATH,
        recognizer_path=FACE_RECOGNIZER_PATH,
        similarity_threshold=FACE_SIMILARITY_THRESHOLD,
    )
    registry = FaceRegistry(FACE_REGISTRY_PATH)
    return model, pose, engine, registry


async def start_vision_services() -> None:
    """Load all vision models once without blocking FastAPI's event loop."""
    global yolo_model, pose_model, face_engine, face_registry
    yolo_model, pose_model, face_engine, face_registry = await asyncio.to_thread(_load_services)


def stop_vision_services() -> None:
    global yolo_model, pose_model, face_engine, face_registry
    yolo_model = None
    pose_model = None
    face_engine = None
    face_registry = None


def health_snapshot() -> dict[str, Any]:
    return {
        "status": "ok" if yolo_model is not None and pose_model is not None and face_engine is not None else "loading",
        "model": MODEL_PATH.name,
        "ppe_model": MODEL_PATH.name,
        "pose_model": Path(POSE_MODEL_SPEC).name,
        "device": DEVICE or "auto",
        "face_detector": FACE_DETECTOR_PATH.name,
        "face_recognizer": FACE_RECOGNIZER_PATH.name,
        "face_profiles": face_registry.count() if face_registry else 0,
        "face_similarity_threshold": FACE_SIMILARITY_THRESHOLD,
    }


def decode_jpeg(encoded: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise FaceServiceError("The uploaded file is not a valid JPEG image.")
    return image


async def read_registration_images(files: list[UploadFile]) -> list[np.ndarray]:
    if len(files) != 5:
        raise HTTPException(status_code=422, detail="Registration requires exactly five JPEG images.")
    images: list[np.ndarray] = []
    for index, upload in enumerate(files, start=1):
        try:
            encoded = await upload.read(MAX_FRAME_BYTES + 1)
            if len(encoded) > MAX_FRAME_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Registration image {index} exceeds the {MAX_FRAME_BYTES}-byte limit.",
                )
            images.append(decode_jpeg(encoded))
        except FaceServiceError as exc:
            raise HTTPException(status_code=422, detail=f"Image {index}: {exc}") from exc
        finally:
            await upload.close()
    return images


def require_face_services() -> tuple[FaceEngine, FaceRegistry]:
    if face_engine is None or face_registry is None:
        raise HTTPException(status_code=503, detail="Face recognition is still loading.")
    return face_engine, face_registry


def require_face_registry() -> FaceRegistry:
    """Return the registry without coupling data deletion to model readiness."""
    global face_registry
    if face_registry is None:
        try:
            face_registry = FaceRegistry(FACE_REGISTRY_PATH)
        except FaceServiceError as exc:
            raise HTTPException(status_code=503, detail=f"Face registry is unavailable: {exc}") from exc
    return face_registry


@router.get("/api/faces")
async def list_faces() -> dict[str, Any]:
    _, registry = require_face_services()
    return {"profiles": registry.list_profiles()}


@router.post("/api/faces", status_code=201)
async def register_face(
    person_id: str = Form(...),
    name: str = Form(...),
    images: list[UploadFile] = File(...),
) -> dict[str, Any]:
    engine, registry = require_face_services()
    captures = await read_registration_images(images)
    try:
        async with vision_lock:
            embedding = await asyncio.to_thread(engine.enrollment_embedding, captures)
        profile = await asyncio.to_thread(registry.create, person_id, name, embedding)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FaceServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"profile": profile}


@router.put("/api/faces/{person_id}")
async def reenroll_face(
    person_id: str,
    images: list[UploadFile] = File(...),
) -> dict[str, Any]:
    engine, registry = require_face_services()
    try:
        person_id = validate_person_id(person_id)
    except FaceServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    captures = await read_registration_images(images)
    try:
        async with vision_lock:
            embedding = await asyncio.to_thread(engine.enrollment_embedding, captures)
        profile = await asyncio.to_thread(registry.replace_embedding, person_id, embedding)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Profile {person_id} was not found.") from exc
    except FaceServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"profile": profile}


@router.delete("/api/faces/{person_id}", status_code=204)
async def delete_face(person_id: str) -> Response:
    _, registry = require_face_services()
    try:
        deleted = await asyncio.to_thread(registry.delete, person_id)
    except FaceServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Profile {person_id.upper()} was not found.")
    return Response(status_code=204)


def lookup_worker_details(person_id: str | None) -> dict[str, Any] | None:
    if not person_id:
        return None
    try:
        db = SessionLocal()
        try:
            worker = (
                db.query(Worker)
                .filter(Worker.employee_code.ilike(person_id.strip()))
                .one_or_none()
            )
            if worker:
                score = (
                    db.query(SafetyScore)
                    .filter(SafetyScore.worker_id == worker.worker_id)
                    .order_by(SafetyScore.calculated_at.desc(), SafetyScore.score_id.desc())
                    .first()
                )
                return {
                    "worker_id": worker.worker_id,
                    "id": worker.employee_code,
                    "workerId": worker.employee_code,
                    "name": worker.name,
                    "department": worker.department.name if worker.department else "Unassigned",
                    "designation": None,
                    "rfidId": worker.rfid_uid or f"RFID-{worker.employee_code}",
                    "ppeScore": round(float(score.compliance_rate), 1) if score else 100.0,
                    "risk": score.risk_level if score else "LOW",
                    "violations": score.violation_count if score else 0,
                    "status": worker.status,
                }
        finally:
            db.close()
    except Exception:
        pass
    return None


def infer_frame(
    encoded_frame: bytes, confidence: float, tracker: PersonTracker | None = None
) -> tuple[
    bytes,
    list[dict[str, Any]],
    float,
    list[dict[str, Any]],
    float,
    str | None,
    dict[str, Any],
    list[dict[str, Any]],
    float,
]:
    """Run pose-guided PPE detection and face recognition for one JPEG frame."""
    if yolo_model is None or pose_model is None or face_engine is None or face_registry is None:
        raise RuntimeError("The vision models are not loaded.")

    image = decode_jpeg(encoded_frame)

    # YOLO PPE detection.
    yolo_started = time.perf_counter()
    results = yolo_model.predict(
        source=image,
        conf=confidence,
        imgsz=IMAGE_SIZE,
        device=DEVICE,
        verbose=False,
    )
    yolo_ms = (time.perf_counter() - yolo_started) * 1000
    result = results[0]

    detections: list[dict[str, Any]] = []
    conf_scores: list[float] = []

    if result.boxes is not None:
        for box in result.boxes:
            class_id = int(box.cls[0].item())
            label = str(result.names[class_id])
            confidence_score = float(box.conf[0].item())
            x1, y1, x2, y2 = (
                round(float(value), 1) for value in box.xyxy[0].tolist()
            )

            detections.append(
                {
                    "class_id": class_id,
                    "label": label,
                    "confidence": round(confidence_score, 4),
                    "bbox": [x1, y1, x2, y2],
                }
            )
            conf_scores.append(confidence_score)

    detection_count = len(detections)
    annotated = result.plot()

    # Pose inference provides the anatomical regions used to validate worn PPE.
    pose_started = time.perf_counter()
    pose_results = pose_model.predict(
        source=image,
        conf=POSE_CONFIDENCE,
        imgsz=IMAGE_SIZE,
        device=DEVICE,
        verbose=False,
    )
    pose_ms = (time.perf_counter() - pose_started) * 1000
    pose_result = pose_results[0]
    people: list[dict[str, Any]] = []
    if pose_result.boxes is not None and pose_result.keypoints is not None:
        keypoint_data = pose_result.keypoints.data.cpu().tolist()
        for index, box in enumerate(pose_result.boxes):
            x1, y1, x2, y2 = (round(float(value), 1) for value in box.xyxy[0].tolist())
            people.append(
                {
                    "bbox": [x1, y1, x2, y2],
                    "confidence": round(float(box.conf[0].item()), 4),
                    "keypoints": keypoint_data[index],
                }
            )

    person_results = analyze_compliance(
        people,
        detections,
        tracker or PersonTracker(),
        image.shape,
        keypoint_threshold=POSE_CONFIDENCE,
        overlap_threshold=PPE_REGION_OVERLAP,
        min_height_ratio=settings.entry_person_min_height_ratio,
        frame_margin_ratio=settings.entry_frame_margin_ratio,
    )
    annotated = annotate_compliance(annotated, person_results, detections)

    primary_compliance = person_results[0] if len(person_results) == 1 else None
    ppe_status = {
        label: bool(primary_compliance and primary_compliance[label] == "YES")
        for label in PPE_ITEM_SPECS
    }
    missing_items = [
        spec["display_name"]
        for label, spec in PPE_ITEM_SPECS.items()
        if primary_compliance and primary_compliance[label] == "NO"
    ]

    # Face recognition runs on the original image while annotation is layered
    # on top of the YOLO-rendered frame.
    faces: list[dict[str, Any]] = []
    face_error: str | None = None
    face_started = time.perf_counter()
    try:
        faces = face_engine.recognize(image, face_registry.embeddings())
        annotated = annotate_faces(annotated, faces)
    except Exception as exc:  # Keep PPE streaming if a single face frame fails.
        face_error = str(exc)
    face_ms = (time.perf_counter() - face_started) * 1000

    # Determine recognized worker information.
    primary_recognized = next((face for face in faces if face.get("recognized")), None)
    if primary_recognized:
        person_id = primary_recognized.get("person_id")
        db_worker = lookup_worker_details(person_id)
        if db_worker:
            worker_data = db_worker
            worker_data["similarity"] = primary_recognized.get("similarity")
            worker_data["recognized"] = True
        else:
            worker_data = {
                "id": person_id or "WK10234",
                "workerId": person_id or "WK10234",
                "name": primary_recognized.get("name", "Recognized Worker"),
                "department": "Mining",
                "designation": "Shift A",
                "rfidId": f"RFID-{person_id}" if person_id else "RFID-8F31A9",
                "ppeScore": 95.0,
                "risk": "LOW",
                "violations": 0,
                "status": "ACTIVE",
                "similarity": primary_recognized.get("similarity"),
                "recognized": True,
            }
    elif faces:
        worker_data = {
            "id": "UNKNOWN",
            "workerId": "UNREGISTERED",
            "name": "Unknown Worker",
            "department": "Unassigned",
            "designation": "—",
            "rfidId": "—",
            "ppeScore": 0,
            "risk": "HIGH",
            "violations": 1,
            "status": "UNREGISTERED",
            "similarity": faces[0].get("similarity"),
            "recognized": False,
        }
    else:
        worker_data = {
            "id": "—",
            "workerId": "—",
            "name": "No Person Detected",
            "department": "—",
            "designation": "—",
            "rfidId": "—",
            "ppeScore": 0,
            "risk": "LOW",
            "violations": 0,
            "status": "IDLE",
            "similarity": None,
            "recognized": False,
        }

    # Calculate overall AI confidence.
    avg_yolo_conf = (sum(conf_scores) / len(conf_scores)) if conf_scores else 0.0
    face_similarity = primary_recognized.get("similarity") if primary_recognized else None
    if face_similarity is not None:
        face_sim = float(face_similarity)
        if avg_yolo_conf > 0:
            ai_confidence = round(face_sim * 40.0 + avg_yolo_conf * 60.0, 1)
        else:
            ai_confidence = round(face_sim * 100.0, 1)
    elif avg_yolo_conf > 0:
        ai_confidence = round(avg_yolo_conf * 100.0, 1)
    else:
        ai_confidence = 0.0

    if not faces and not person_results and detection_count == 0:
        decision = "IDLE"
    elif primary_compliance and primary_compliance["status"] == "COMPLIANT" and primary_recognized:
        decision = "ENTRY ALLOWED"
    elif primary_compliance and primary_compliance["status"] == "UNKNOWN":
        decision = "ANALYZING"
    else:
        decision = "ENTRY DENIED"

    live_summary = {
        "worker": worker_data,
        "ppe": ppe_status,
        "missing": missing_items,
        "aiConfidence": ai_confidence,
        "decision": decision,
    }

    encoded_ok, encoded = cv2.imencode(
        ".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 82]
    )
    if not encoded_ok:
        raise RuntimeError("OpenCV could not encode the annotated frame.")

    return (
        encoded.tobytes(),
        detections,
        yolo_ms,
        faces,
        face_ms,
        face_error,
        live_summary,
        person_results,
        pose_ms,
    )
