import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.voice import VoiceSessionStart, VoiceSessionStop
from app.services.voice_tools import (
    LIST_RECENT_WORKERS_TOOL,
    LIST_WORKER_NAMES_TOOL,
    execute_list_recent_workers,
    execute_list_worker_names,
)

logger = logging.getLogger("suraksha.voice")

SYSTEM_INSTRUCTION = """
You are SURAKSHA, a concise and calm voice assistant for a mine-safety application.
Speak naturally and keep answers short enough for voice playback. Reply in the language used by
the user. You may explain how attendance, PPE compliance, violations, and worker safety workflows
operate in general.

Use list_worker_names whenever the user asks who the workers are, requests all worker names, or
needs help identifying a worker. Use list_recent_workers when the user asks which workers were
added recently, today, or in the last 24 hours. Employee codes are provided only to disambiguate
duplicate names.

Attendance, violations, safety scores, and all other operational-data access are not connected yet.
If asked for those values, clearly say they are unavailable. Never guess or fabricate data. Do not
mention internal implementation details unless the user explicitly asks.
""".strip()


@dataclass
class VoiceRuntime:
    session_id: str
    websocket: WebSocket
    settings: Settings
    audio_queue: asyncio.Queue[bytes] = field(
        default_factory=lambda: asyncio.Queue(maxsize=150)
    )
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    websocket_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    gemini_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    client_audio_frames: int = 0
    gemini_audio_chunks: int = 0

    async def send_json(self, payload: dict[str, Any]) -> None:
        payload.setdefault("sessionId", self.session_id)
        async with self.websocket_lock:
            await self.websocket.send_json(payload)

    async def send_bytes(self, payload: bytes) -> None:
        async with self.websocket_lock:
            await self.websocket.send_bytes(payload)


def _genai_modules() -> tuple[Any, Any]:
    # Keep the rest of SURAKSHA bootable before the optional voice dependency is installed.
    from google import genai
    from google.genai import types

    return genai, types


def live_config() -> Any:
    _, types = _genai_modules()
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(language_code="en-IN"),
        system_instruction=SYSTEM_INSTRUCTION,
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        thinking_config=types.ThinkingConfig(thinking_level="minimal"),
        tools=[
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=LIST_WORKER_NAMES_TOOL,
                        description=(
                            "Return every worker name and employee code, sorted by name. "
                            "Use this to list workers or disambiguate a spoken worker name."
                        ),
                        parameters_json_schema={"type": "object", "properties": {}},
                    ),
                    types.FunctionDeclaration(
                        name=LIST_RECENT_WORKERS_TOOL,
                        description=(
                            "Return workers added during the rolling 24 hours immediately before "
                            "the current time, newest first."
                        ),
                        parameters_json_schema={"type": "object", "properties": {}},
                    ),
                ]
            )
        ],
    )


async def receive_start(websocket: WebSocket) -> VoiceSessionStart:
    return VoiceSessionStart.model_validate_json(await websocket.receive_text())


async def _receive_from_browser(runtime: VoiceRuntime) -> None:
    try:
        while not runtime.stop_event.is_set():
            event = await runtime.websocket.receive()
            if event["type"] == "websocket.disconnect":
                break
            audio = event.get("bytes")
            if audio:
                runtime.client_audio_frames += 1
                await runtime.audio_queue.put(audio)
                continue
            text = event.get("text")
            if not text:
                continue
            payload = json.loads(text)
            if payload.get("sessionId") != runtime.session_id:
                continue
            if payload.get("type") == "session.stop":
                VoiceSessionStop.model_validate(payload)
                break
    except (WebSocketDisconnect, RuntimeError):
        pass
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("Invalid voice client event session=%s: %s", runtime.session_id[:8], exc)
        with contextlib.suppress(RuntimeError, WebSocketDisconnect):
            await runtime.send_json(
                {
                    "type": "error",
                    "code": "invalid_client_event",
                    "message": str(exc),
                    "recoverable": True,
                }
            )
    finally:
        runtime.stop_event.set()


async def _send_audio_to_gemini(runtime: VoiceRuntime, live_session: Any) -> None:
    _, types = _genai_modules()
    while not runtime.stop_event.is_set():
        audio = await runtime.audio_queue.get()
        async with runtime.gemini_lock:
            await live_session.send_realtime_input(
                audio=types.Blob(data=audio, mime_type="audio/pcm;rate=16000")
            )


async def _receive_from_gemini(runtime: VoiceRuntime, live_session: Any) -> None:
    while not runtime.stop_event.is_set():
        async for response in live_session.receive():
            if runtime.stop_event.is_set():
                return
            content = response.server_content
            sent_audio = False
            if content:
                if content.input_transcription and content.input_transcription.text:
                    await runtime.send_json(
                        {
                            "type": "transcript",
                            "speaker": "user",
                            "text": content.input_transcription.text,
                        }
                    )
                if content.output_transcription and content.output_transcription.text:
                    await runtime.send_json(
                        {
                            "type": "transcript",
                            "speaker": "agent",
                            "text": content.output_transcription.text,
                        }
                    )
                if content.interrupted:
                    await runtime.send_json({"type": "audio.clear"})
                if content.model_turn:
                    for part in content.model_turn.parts or []:
                        if part.inline_data and part.inline_data.data:
                            runtime.gemini_audio_chunks += 1
                            await runtime.send_json({"type": "status", "state": "speaking"})
                            await runtime.send_bytes(part.inline_data.data)
                            sent_audio = True
                if content.turn_complete:
                    await runtime.send_json({"type": "status", "state": "listening"})

            if not sent_audio and response.data:
                runtime.gemini_audio_chunks += 1
                await runtime.send_json({"type": "status", "state": "speaking"})
                await runtime.send_bytes(response.data)

            if response.tool_call:
                await runtime.send_json({"type": "status", "state": "processing"})
                await _handle_tool_calls(runtime, live_session, response.tool_call)


async def _handle_tool_calls(runtime: VoiceRuntime, live_session: Any, tool_call: Any) -> None:
    _, types = _genai_modules()
    responses = []
    for function_call in tool_call.function_calls:
        if function_call.name in {LIST_WORKER_NAMES_TOOL, LIST_RECENT_WORKERS_TOOL}:
            try:
                executor = (
                    execute_list_worker_names
                    if function_call.name == LIST_WORKER_NAMES_TOOL
                    else execute_list_recent_workers
                )
                result = await asyncio.to_thread(executor)
                payload = {"ok": True, "result": result}
                logger.info(
                    "Voice tool completed session=%s tool=%s count=%d",
                    runtime.session_id[:8],
                    function_call.name,
                    result["count"],
                )
            except Exception:
                logger.exception(
                    "Voice tool failed session=%s tool=%s",
                    runtime.session_id[:8],
                    function_call.name,
                )
                payload = {"ok": False, "error": "worker_lookup_failed"}
        else:
            payload = {"ok": False, "error": "unknown_tool"}

        responses.append(
            types.FunctionResponse(
                id=function_call.id,
                name=function_call.name,
                response=payload,
            )
        )

    async with runtime.gemini_lock:
        await live_session.send_tool_response(function_responses=responses)


async def run_voice_session(
    websocket: WebSocket,
    start: VoiceSessionStart,
    settings: Settings,
) -> None:
    runtime = VoiceRuntime(start.sessionId, websocket, settings)
    if not settings.google_api_key:
        await runtime.send_json(
            {
                "type": "error",
                "code": "missing_google_api_key",
                "message": "The voice service is missing GOOGLE_API_KEY.",
                "recoverable": False,
            }
        )
        return

    try:
        genai, _ = _genai_modules()
    except ImportError:
        await runtime.send_json(
            {
                "type": "error",
                "code": "missing_voice_dependency",
                "message": "Install the backend requirements to enable voice sessions.",
                "recoverable": False,
            }
        )
        return

    client = genai.Client(
        api_key=settings.google_api_key,
        http_options={"api_version": "v1beta"},
    )
    await runtime.send_json({"type": "status", "state": "connecting"})
    try:
        async with client.aio.live.connect(
            model=settings.gemini_live_model,
            config=live_config(),
        ) as live_session:
            await runtime.send_json({"type": "status", "state": "listening"})
            tasks = [
                asyncio.create_task(_receive_from_browser(runtime)),
                asyncio.create_task(_send_audio_to_gemini(runtime, live_session)),
                asyncio.create_task(_receive_from_gemini(runtime, live_session)),
            ]
            stop_waiter = asyncio.create_task(runtime.stop_event.wait())
            finished, _ = await asyncio.wait(
                [*tasks, stop_waiter], return_when=asyncio.FIRST_COMPLETED
            )
            failure = next(
                (
                    task.exception()
                    for task in finished
                    if task is not stop_waiter
                    and not task.cancelled()
                    and task.exception()
                ),
                None,
            )
            runtime.stop_event.set()
            stop_waiter.cancel()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, stop_waiter, return_exceptions=True)
            if failure:
                raise failure
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Gemini Live session failed session=%s", runtime.session_id[:8])
        with contextlib.suppress(RuntimeError, WebSocketDisconnect):
            await runtime.send_json(
                {
                    "type": "error",
                    "code": "gemini_session_failed",
                    "message": f"Gemini Live session failed: {exc}",
                    "recoverable": True,
                }
            )
    finally:
        runtime.stop_event.set()
        logger.info(
            "Voice session closed session=%s input_frames=%d output_chunks=%d",
            runtime.session_id[:8],
            runtime.client_audio_frames,
            runtime.gemini_audio_chunks,
        )
