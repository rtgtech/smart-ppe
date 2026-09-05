from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes import assistant_queries, entry, operations, voice, workers
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.init_db import init_db
from app.services.vision import (
    health_snapshot,
    router as vision_router,
    start_vision_services,
    stop_vision_services,
)


# Configure logging before application startup.
configure_logging()

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

    if settings.deployment_role != "central":
        await start_vision_services()

    await entry.start_entry_services()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await entry.stop_entry_services()
    stop_vision_services()


@app.get("/health")
def health_check() -> dict[str, Any]:
    return {
        "status": "ok",
        "role": settings.deployment_role,
        "vision": (
            health_snapshot()
            if settings.deployment_role != "central"
            else {"status": "disabled"}
        ),
    }


app.include_router(
    workers.router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    operations.router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    entry.router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    assistant_queries.router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    voice.router,
    prefix=settings.api_v1_prefix,
)

app.include_router(vision_router)
