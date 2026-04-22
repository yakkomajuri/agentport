from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from httpx import ASGITransport, AsyncClient

from agent_port.config import settings
from agent_port.main import (
    ASSET_CACHE_CONTROL,
    HTML_CACHE_CONTROL,
    _ImmutableAssetStaticFiles,
    _ui_file_response,
    app,
    validate_startup_settings,
)


def test_validate_startup_settings_rejects_default_jwt_secret(monkeypatch):
    monkeypatch.setattr(settings, "dev", False)
    monkeypatch.setattr(settings, "jwt_secret_key", "change-me-in-production")

    with pytest.raises(RuntimeError, match="default JWT secret key"):
        validate_startup_settings()


def test_validate_startup_settings_accepts_configured_jwt_secret(monkeypatch):
    monkeypatch.setattr(settings, "dev", False)
    monkeypatch.setattr(settings, "jwt_secret_key", "super-secret-for-tests")

    validate_startup_settings()


def test_app_enables_gzip_middleware():
    gzip_middleware = next((mw for mw in app.user_middleware if mw.cls is GZipMiddleware), None)

    assert gzip_middleware is not None
    assert gzip_middleware.kwargs["minimum_size"] == 500


@pytest.mark.anyio
async def test_immutable_asset_static_files_adds_cache_control(tmp_path: Path):
    asset_dir = tmp_path / "assets"
    asset_dir.mkdir()
    (asset_dir / "app.js").write_text("console.log('AgentPort')")

    test_app = FastAPI()
    test_app.mount("/assets", _ImmutableAssetStaticFiles(directory=asset_dir), name="assets")

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/assets/app.js")

    assert response.status_code == 200
    assert response.headers["cache-control"] == ASSET_CACHE_CONTROL


def test_ui_file_response_can_disable_caching(tmp_path: Path):
    index_file = tmp_path / "index.html"
    index_file.write_text("<!doctype html>")

    response = _ui_file_response(index_file, cache_control=HTML_CACHE_CONTROL)

    assert response.headers["cache-control"] == HTML_CACHE_CONTROL
