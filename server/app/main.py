from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes import operations, workers
from app.core.config import get_settings
from app.db.init_db import init_db
from app.services.vision import (
    health_snapshot,
    router as vision_router,
    start_vision_services,
    stop_vision_services,
)

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    await start_vision_services()


@app.on_event("shutdown")
def on_shutdown() -> None:
    stop_vision_services()


@app.get("/health")
def health_check() -> dict[str, Any]:
    return {"status": "ok", "vision": health_snapshot()}


app.include_router(workers.router, prefix=settings.api_v1_prefix)
app.include_router(operations.router, prefix=settings.api_v1_prefix)
app.include_router(vision_router)
