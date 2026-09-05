from typing import Literal

from pydantic import BaseModel


class VoiceSessionStart(BaseModel):
    type: Literal["session.start"]
    sessionId: str
    mode: Literal["toggle", "push-to-talk"]


class VoiceSessionStop(BaseModel):
    type: Literal["session.stop"]
    sessionId: str
    reason: str = "user-stopped"
