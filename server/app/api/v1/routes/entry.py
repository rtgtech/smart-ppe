"""Transient entry API and annotated camera WebSocket."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Header, HTTPException, Response, WebSocket, WebSocketDisconnect

from app.services.entry_pipeline import entry_sessions
from app.services.ppe_compliance import PersonTracker
from app.services.vision import MAX_FRAME_BYTES, identity_frame, ppe_frame, vision_lock


router = APIRouter(prefix="/entry", tags=["entry"])
_locks: dict[str, asyncio.Lock] = {}


def _session(session_id: str):
    session = entry_sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Entry session not found")
    return session


@router.post("/attempts", status_code=201)
async def create_attempt(idempotency_key: str = Header(..., alias="Idempotency-Key")):
    try:
        session_id = str(uuid.UUID(idempotency_key))
    except ValueError as exc:
        raise HTTPException(422, "Idempotency-Key must be a UUID") from exc
    return entry_sessions.create(session_id).result()


@router.get("/attempts/{session_id}")
async def get_attempt(session_id: str):
    return _session(session_id).result()


@router.delete("/attempts/{session_id}", status_code=204)
async def discard_attempt(session_id: str) -> Response:
    entry_sessions.discard(session_id)
    _locks.pop(session_id, None)
    return Response(status_code=204)


@router.post("/attempts/{session_id}/finalize")
async def finalize_attempt(session_id: str):
    session = _session(session_id)
    if session.lifecycle == "ACTIVE":
        session.finish("HOLD", ["SCAN_CANCELLED"])
    return session.result()


@router.websocket("/attempts/{session_id}/stream")
async def stream(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    session = entry_sessions.get(session_id)
    if not session:
        await websocket.send_json({"type": "error", "message": "Entry session not found"})
        await websocket.close(code=1008)
        return
    await websocket.send_json({"type": "entry_meta", "entry": session.result()})
    tracker, lock = PersonTracker(), _locks.setdefault(session_id, asyncio.Lock())
    try:
        while session.lifecycle == "ACTIVE":
            message = await websocket.receive()
            frame = message.get("bytes")
            if not frame:
                continue
            if len(frame) > MAX_FRAME_BYTES:
                await websocket.send_json({"type": "error", "message": "Frame is too large"})
                continue
            try:
                async with lock, vision_lock:
                    if session.phase == "IDENTITY":
                        output, faces, quality, face_ms = await asyncio.to_thread(identity_frame, frame)
                        session.add_identity(faces, quality["valid"])
                        metadata = {"faces": faces, "face_inference_ms": round(face_ms, 1)}
                    else:
                        output, detections, persons, faces, quality, timings = await asyncio.to_thread(ppe_frame, frame, tracker)
                        session.add_ppe(persons, faces, quality["valid"])
                        metadata = {"faces": faces, "persons": persons, "detections": detections, **timings}
                await websocket.send_json({"type": "frame_meta", "entry": session.result(), "quality": quality, **metadata})
                await websocket.send_bytes(output)
                if session.lifecycle == "FINALIZED":
                    await websocket.send_json({"type": "session_complete", "entry": session.result()})
                    break
            except Exception as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        _locks.pop(session_id, None)


@router.get("/sync/status")
async def sync_status():
    return {"network": "NOT_CONFIGURED", "pending": 0, "failed": 0, "last_sync": None, "events": []}


async def start_entry_services() -> None:
    pass


async def stop_entry_services() -> None:
    entry_sessions.sessions.clear()
