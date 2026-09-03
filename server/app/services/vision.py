"""Real-time YOLO PPE detection and local face identification services."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, WebSocket, WebSocketDisconnect
from ultralytics import YOLO

from app.db.session import SessionLocal
from app.models import SafetyScore, Worker
from app.services.face_recognition import (
    FaceEngine,
    FaceRegistry,
    FaceServiceError,
    annotate_faces,
    validate_person_id,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
STREAM_SERVER_DIR = REPOSITORY_ROOT / "stream_test" / "server"

MODEL_PATH = Path(
    os.getenv("YOLO_MODEL_PATH", str(REPOSITORY_ROOT / "best.pt"))
).expanduser().resolve()
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

router = APIRouter(tags=["vision"])
vision_lock = asyncio.Lock()
yolo_model: YOLO | None = None
face_engine: FaceEngine | None = None
face_registry: FaceRegistry | None = None


def _load_services() -> tuple[YOLO, FaceEngine, FaceRegistry]:
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"YOLO weights not found at '{MODEL_PATH}'. Set YOLO_MODEL_PATH to a local .pt file."
        )
    model = YOLO(str(MODEL_PATH))
    engine = FaceEngine(
        detector_path=FACE_DETECTOR_PATH,
        recognizer_path=FACE_RECOGNIZER_PATH,
        similarity_threshold=FACE_SIMILARITY_THRESHOLD,
    )
    registry = FaceRegistry(FACE_REGISTRY_PATH)
    return model, engine, registry


async def start_vision_services() -> None:
    """Load all vision models once without blocking FastAPI's event loop."""
    global yolo_model, face_engine, face_registry
    yolo_model, face_engine, face_registry = await asyncio.to_thread(_load_services)


def stop_vision_services() -> None:
    global yolo_model, face_engine, face_registry
    yolo_model = None
    face_engine = None
    face_registry = None


def health_snapshot() -> dict[str, Any]:
    return {
        "status": "ok" if yolo_model is not None and face_engine is not None else "loading",
        "model": MODEL_PATH.name,
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
                    "department": worker.department.name if worker.department else "Underground Mining",
                    "designation": worker.designation,
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
    encoded_frame: bytes, confidence: float
) -> tuple[
    bytes,
    list[dict[str, Any]],
    float,
    list[dict[str, Any]],
    float,
    str | None,
    dict[str, Any],
]:
    """Run PPE detection and face recognition for one JPEG frame."""
    if yolo_model is None or face_engine is None or face_registry is None:
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
    detected_classes: set[str] = set()
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
            detected_classes.add(label.lower())
            conf_scores.append(confidence_score)

    detection_count = len(detections)
    annotated = result.plot()

    # Calculate PPE presence from YOLO classes.
    has_helmet = "helmet" in detected_classes and "no_helmet" not in detected_classes
    has_boots = "boots" in detected_classes and "no_boots" not in detected_classes
    has_vest = "vest" in detected_classes
    has_gloves = "gloves" in detected_classes and "no_gloves" not in detected_classes
    has_goggles = (
        "goggles" in detected_classes
        and "no_goggle" not in detected_classes
        and "no_goggles" not in detected_classes
    )

    # Cap lamp is treated as attached to a valid helmet.
    has_cap_lamp = has_helmet

    ppe_status = {
        "helmet": has_helmet,
        "capLamp": has_cap_lamp,
        "safetyBoots": has_boots,
        "reflectiveVest": has_vest,
        "gloves": has_gloves,
        "goggles": has_goggles,
    }

    missing_items: list[str] = []
    if not has_helmet:
        missing_items.append("Helmet")
    if not has_cap_lamp:
        missing_items.append("Cap Lamp")
    if not has_boots:
        missing_items.append("Safety Boots")
    if not has_vest:
        missing_items.append("Reflective Vest")

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
                "department": "Underground Mining",
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

    if not faces and detection_count == 0:
        decision = "IDLE"
    elif not missing_items and primary_recognized:
        decision = "ENTRY ALLOWED"
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
    )


@router.websocket("/ws/inference")
async def inference_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json(
        {
            "type": "ready",
            "model": MODEL_PATH.name,
            "device": DEVICE or "auto",
            "face_recognition": True,
            "face_similarity_threshold": FACE_SIMILARITY_THRESHOLD,
        }
    )
    confidence = 0.5

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            text = message.get("text")
            if text is not None:
                try:
                    config = json.loads(text)
                    if config.get("type") == "config":
                        confidence = min(
                            0.99,
                            max(0.01, float(config.get("confidence", 0.5))),
                        )
                except (json.JSONDecodeError, TypeError, ValueError):
                    try:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": "Invalid JSON configuration message.",
                            }
                        )
                    except Exception:
                        break
                continue

            frame = message.get("bytes")
            if frame is None:
                continue

            if len(frame) > MAX_FRAME_BYTES:
                try:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": f"Frame exceeds the {MAX_FRAME_BYTES}-byte limit.",
                        }
                    )
                except Exception:
                    break
                continue

            try:
                async with vision_lock:
                    (
                        output,
                        detections,
                        yolo_ms,
                        faces,
                        face_ms,
                        face_error,
                        live_summary,
                    ) = await asyncio.to_thread(infer_frame, frame, confidence)

                metadata: dict[str, Any] = {
                    "type": "frame_meta",
                    "detection_count": len(detections),
                    "detections": detections,
                    "inference_ms": round(yolo_ms, 1),
                    "face_inference_ms": round(face_ms, 1),
                    "recognized_faces": sum(
                        bool(face.get("recognized")) for face in faces
                    ),
                    "faces": faces,
                    "worker": live_summary["worker"],
                    "ppe": live_summary["ppe"],
                    "missing": live_summary["missing"],
                    "aiConfidence": live_summary["aiConfidence"],
                    "decision": live_summary["decision"],
                }
                if face_error:
                    metadata["face_error"] = face_error

                await websocket.send_json(metadata)
                await websocket.send_bytes(output)
            except Exception as exc:
                try:
                    await websocket.send_json({"type": "error", "message": str(exc)})
                except Exception:
                    break
    except (WebSocketDisconnect, RuntimeError):
        pass
