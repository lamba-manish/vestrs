"""Shared pytest fixtures for the api test suite."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.main import app as real_app


@pytest.fixture
def app() -> FastAPI:
    return real_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    # raise_app_exceptions=False: Starlette's ServerErrorMiddleware re-raises
    # after handing the exception to our handler (so uvicorn can log it). In
    # tests we want to assert on the response, not unwrap the exception.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
