from functools import lru_cache
import os
from pathlib import Path

# pyrefly: ignore [missing-import]
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "SURAKSHA API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = os.getenv("SURAKSHA_DATABASE_URL", f"sqlite:///{Path(__file__).resolve().parents[3] / 'data' / 'suraksha.db'}")
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    deployment_role: str = os.getenv("SURAKSHA_ROLE", "edge").lower()
    edge_device_serial: str = os.getenv("EDGE_DEVICE_SERIAL", "AI-CAM-G01")
    central_sync_url: str = os.getenv("CENTRAL_SYNC_URL", "").rstrip("/")
    sync_api_token: str = os.getenv("SYNC_API_TOKEN", "")
    entry_identity_timeout_seconds: float = float(os.getenv("ENTRY_IDENTITY_TIMEOUT_SECONDS", "10"))
    entry_evidence_timeout_seconds: float = float(os.getenv("ENTRY_EVIDENCE_TIMEOUT_SECONDS", "15"))
    entry_person_min_height_ratio: float = float(os.getenv("ENTRY_PERSON_MIN_HEIGHT_RATIO", "0.60"))
    entry_frame_margin_ratio: float = float(os.getenv("ENTRY_FRAME_MARGIN_RATIO", "0.02"))
    entry_min_laplacian_variance: float = float(os.getenv("ENTRY_MIN_LAPLACIAN_VARIANCE", "80"))
    entry_min_luminance: float = float(os.getenv("ENTRY_MIN_LUMINANCE", "40"))
    entry_max_luminance: float = float(os.getenv("ENTRY_MAX_LUMINANCE", "220"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
