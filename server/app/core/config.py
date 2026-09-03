from functools import lru_cache
from pathlib import Path

# pyrefly: ignore [missing-import]
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "SURAKSHA API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = f"sqlite:///{Path(__file__).resolve().parents[3] / 'data' / 'suraksha.db'}"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
