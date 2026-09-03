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


def infer_frame(
    encoded_frame: bytes, confidence: float
) -> tuple[bytes, int, float, list[dict[str, Any]], float, str | None]:
    if yolo_model is None or face_engine is None or face_registry is None:
        raise RuntimeError("The vision models are not loaded.")

    image = decode_jpeg(encoded_frame)
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
    detection_count = 0 if result.boxes is None else len(result.boxes)
    annotated = result.plot()

    faces: list[dict[str, Any]] = []
    face_error: str | None = None
    face_started = time.perf_counter()
    try:
        faces = face_engine.recognize(image, face_registry.embeddings())
        annotated = annotate_faces(annotated, faces)
    except Exception as exc:  # Keep PPE streaming if a single face frame fails.
        face_error = str(exc)
    face_ms = (time.perf_counter() - face_started) * 1000

    encoded_ok, encoded = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 82])
    if not encoded_ok:
        raise RuntimeError("OpenCV could not encode the annotated frame.")
    return encoded.tobytes(), detection_count, yolo_ms, faces, face_ms, face_error


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
                        confidence = min(0.99, max(0.01, float(config.get("confidence", 0.5))))
                except (json.JSONDecodeError, TypeError, ValueError):
                    await websocket.send_json(
                        {"type": "error", "message": "Invalid JSON configuration message."}
                    )
                continue

            frame = message.get("bytes")
            if frame is None:
                continue
            if len(frame) > MAX_FRAME_BYTES:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Frame exceeds the {MAX_FRAME_BYTES}-byte limit.",
                    }
                )
                continue

            try:
                async with vision_lock:
                    output, count, yolo_ms, faces, face_ms, face_error = await asyncio.to_thread(
                        infer_frame, frame, confidence
                    )
                metadata: dict[str, Any] = {
                    "type": "frame_meta",
                    "detections": count,
                    "inference_ms": round(yolo_ms, 1),
                    "face_inference_ms": round(face_ms, 1),
                    "recognized_faces": sum(bool(face["recognized"]) for face in faces),
                    "faces": faces,
                }
                if face_error:
                    metadata["face_error"] = face_error
                await websocket.send_json(metadata)
                await websocket.send_bytes(output)
            except Exception as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})
    except WebSocketDisconnect:
        pass
