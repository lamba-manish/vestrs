"""FastAPI application entrypoint.

Slice 0: minimal app exposing /healthz with the canonical response envelope.
Middleware (request-id, logging), error handler, and the envelope helpers
land in Slice 2.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Vestrs API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict[str, Any]:
    return {
        "success": True,
        "data": {
            "status": "ok",
            "env": settings.app_env.value,
            "version": app.version,
        },
        "request_id": None,
    }
