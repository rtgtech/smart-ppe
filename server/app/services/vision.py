"""Model loading, enrollment endpoints, and stage-specific frame inference."""

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
from app.services.face_recognition import EMBEDDING_MODEL_VERSION, FaceEngine, FaceRegistry, FaceServiceError, annotate_faces, validate_person_id
from app.services.ppe_compliance import PersonTracker, analyze_compliance, annotate_compliance


ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = ROOT / "stream_test" / "server" / "models"
PPE_PATH = Path(os.getenv("YOLO_MODEL_PATH", ROOT / "best2.pt")).resolve()
POSE_PATH = os.getenv("YOLO_POSE_MODEL", str(ROOT / "server" / "yolo11n-pose.pt"))
REGISTRY_PATH = Path(os.getenv("FACE_REGISTRY_PATH", ROOT / "stream_test" / "server" / "data" / "faces.json")).resolve()
MAX_FRAME_BYTES = int(os.getenv("MAX_FRAME_BYTES", "5000000"))
DEVICE = os.getenv("YOLO_DEVICE") or None
settings = get_settings()

router, vision_lock = APIRouter(tags=["vision"]), asyncio.Lock()
ppe_model: YOLO | None = None
pose_model: YOLO | None = None
face_engine: FaceEngine | None = None
face_registry: FaceRegistry | None = None


def _load() -> tuple[YOLO, YOLO, FaceEngine, FaceRegistry]:
    return (
        YOLO(str(PPE_PATH)),
        YOLO(POSE_PATH),
        FaceEngine(
            Path(os.getenv("FACE_DETECTOR_PATH", MODEL_DIR / "scrfd_10g_bnkps.onnx")),
            Path(os.getenv("FACE_RECOGNIZER_PATH", MODEL_DIR / "edgeface_s_gamma_05.pt")),
            float(os.getenv("FACE_SIMILARITY_THRESHOLD", ".4")),
            device=os.getenv("FACE_DEVICE") or DEVICE,
        ),
        FaceRegistry(REGISTRY_PATH),
    )


async def start_vision_services() -> None:
    global ppe_model, pose_model, face_engine, face_registry
    ppe_model, pose_model, face_engine, face_registry = await asyncio.to_thread(_load)


def stop_vision_services() -> None:
    global ppe_model, pose_model, face_engine, face_registry
    ppe_model = pose_model = face_engine = face_registry = None


def health_snapshot() -> dict[str, Any]:
    ready = all(value is not None for value in (ppe_model, pose_model, face_engine, face_registry))
    return {"status": "ok" if ready else "loading", "ppe_model": PPE_PATH.name, "pose_model": Path(POSE_PATH).name, "face_profiles": face_registry.count(EMBEDDING_MODEL_VERSION) if face_registry else 0}


def decode_jpeg(encoded: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(encoded, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise FaceServiceError("Invalid JPEG frame")
    return image


def _quality(image: np.ndarray) -> dict[str, Any]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    light, sharp = float(gray.mean()), float(cv2.Laplacian(gray, cv2.CV_64F).var())
    return {"valid": settings.entry_min_luminance <= light <= settings.entry_max_luminance and sharp >= settings.entry_min_laplacian_variance, "luminance": round(light, 1), "sharpness": round(sharp, 1)}


def _jpeg(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 82])
    if not ok:
        raise RuntimeError("Could not encode inference frame")
    return encoded.tobytes()


def identity_frame(encoded: bytes) -> tuple[bytes, list[dict[str, Any]], dict[str, Any], float]:
    if not face_engine or not face_registry:
        raise RuntimeError("Face recognition is loading")
    image, started = decode_jpeg(encoded), time.perf_counter()
    faces = face_engine.recognize(image, face_registry.embeddings())
    elapsed = (time.perf_counter() - started) * 1000
    return _jpeg(annotate_faces(image.copy(), faces)), faces, _quality(image), elapsed


def ppe_frame(encoded: bytes, tracker: PersonTracker) -> tuple[bytes, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, float]]:
    if not ppe_model or not pose_model or not face_engine or not face_registry:
        raise RuntimeError("Vision models are loading")
    image = decode_jpeg(encoded)
    started = time.perf_counter()
    result = ppe_model.predict(image, conf=.5, imgsz=640, device=DEVICE, verbose=False)[0]
    ppe_ms = (time.perf_counter() - started) * 1000
    detections = []
    for box in result.boxes if result.boxes is not None else []:
        class_id = int(box.cls[0].item())
        detections.append({"label": str(result.names[class_id]).lower(), "confidence": round(float(box.conf[0].item()), 4), "bbox": [round(float(value), 1) for value in box.xyxy[0].tolist()]})

    started = time.perf_counter()
    pose = pose_model.predict(image, conf=.35, imgsz=640, device=DEVICE, verbose=False)[0]
    pose_ms = (time.perf_counter() - started) * 1000
    people = []
    if pose.boxes is not None:
        for box in pose.boxes:
            people.append({"bbox": [round(float(value), 1) for value in box.xyxy[0].tolist()], "confidence": round(float(box.conf[0].item()), 4)})
    persons = analyze_compliance(people, detections, tracker, image.shape)

    started = time.perf_counter()
    faces = face_engine.recognize(image, face_registry.embeddings())
    face_ms = (time.perf_counter() - started) * 1000
    annotated = annotate_faces(annotate_compliance(image.copy(), persons, detections), faces)
    return _jpeg(annotated), detections, persons, faces, _quality(image), {"ppe_ms": round(ppe_ms, 1), "pose_ms": round(pose_ms, 1), "face_ms": round(face_ms, 1)}


def require_face_services() -> tuple[FaceEngine, FaceRegistry]:
    if not face_engine or not face_registry:
        raise HTTPException(503, "Face recognition is loading")
    return face_engine, face_registry


def require_face_registry() -> FaceRegistry:
    global face_registry
    face_registry = face_registry or FaceRegistry(REGISTRY_PATH)
    return face_registry


async def read_registration_images(files: list[UploadFile]) -> list[np.ndarray]:
    if len(files) != 5:
        raise HTTPException(422, "Exactly five face images are required")
    images = []
    for upload in files:
        data = await upload.read(MAX_FRAME_BYTES + 1)
        await upload.close()
        if len(data) > MAX_FRAME_BYTES:
            raise HTTPException(413, "Face image is too large")
        images.append(decode_jpeg(data))
    return images


@router.get("/api/faces")
def list_faces() -> dict[str, Any]:
    return {"profiles": require_face_registry().list_profiles()}


@router.post("/api/faces", status_code=201)
async def register_face(person_id: str = Form(...), name: str = Form(...), images: list[UploadFile] = File(...)) -> dict[str, Any]:
    engine, registry = require_face_services()
    captures = await read_registration_images(images)
    async with vision_lock:
        embedding = await asyncio.to_thread(engine.enrollment_embedding, captures)
    return {"profile": await asyncio.to_thread(registry.create, person_id, name, embedding)}


@router.put("/api/faces/{person_id}")
async def reenroll_face(person_id: str, images: list[UploadFile] = File(...)) -> dict[str, Any]:
    engine, registry = require_face_services()
    captures = await read_registration_images(images)
    async with vision_lock:
        embedding = await asyncio.to_thread(engine.enrollment_embedding, captures)
    return {"profile": await asyncio.to_thread(registry.replace_embedding, validate_person_id(person_id), embedding)}


@router.delete("/api/faces/{person_id}", status_code=204)
async def delete_face(person_id: str) -> Response:
    if not await asyncio.to_thread(require_face_registry().delete, person_id):
        raise HTTPException(404, "Face profile not found")
    return Response(status_code=204)
