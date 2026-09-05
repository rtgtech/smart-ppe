import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from app.core.config import get_settings
from app.services.voice_agent import receive_start, run_voice_session

router = APIRouter(tags=["voice"])
logger = logging.getLogger("suraksha.voice.api")


@router.websocket("/voice/ws")
async def voice_socket(websocket: WebSocket) -> None:
    settings = get_settings()
    origin = websocket.headers.get("origin")
    if origin and origin not in settings.cors_origins:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Origin not allowed",
        )
        return

    await websocket.accept()
    try:
        start = await receive_start(websocket)
        await run_voice_session(websocket, start, settings)
    except (ValidationError, ValueError) as exc:
        await websocket.send_json(
            {
                "type": "error",
                "code": "invalid_session_start",
                "message": str(exc),
                "recoverable": False,
            }
        )
    except WebSocketDisconnect:
        logger.info("Voice websocket disconnected before session completion")
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass
