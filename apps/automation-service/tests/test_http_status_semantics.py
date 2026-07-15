import pytest
import inspect
import importlib
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.v1.deps import get_current_user


def test_general_auth_dependency_does_not_accept_jwt_in_query_string():
    assert "token_query" not in inspect.signature(get_current_user).parameters


def test_legacy_python_identity_endpoints_are_not_exposed():
    exposed_paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/login/login" not in exposed_paths
    assert "/api/login/register" not in exposed_paths
    assert "/api/login/checkUserExists" not in exposed_paths


@pytest.mark.asyncio
async def test_missing_bearer_token_returns_http_401():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/item/list", json={})

    assert response.status_code == 401
    assert response.json()["code"] == 401
    assert response.headers["X-Request-Id"]
    assert response.headers["Cache-Control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Expires"] == "0"


@pytest.mark.asyncio
async def test_unhandled_exception_returns_http_500():
    route_path = "/__tests__/unhandled-error"
    if not any(getattr(route, "path", None) == route_path for route in app.routes):
        async def raise_unhandled_error():
            raise RuntimeError("sensitive internal detail")

        app.add_api_route(route_path, raise_unhandled_error, methods=["GET"])

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(route_path)

    assert response.status_code == 500
    assert response.json() == {"code": 500, "msg": "系统繁忙，请稍后重试", "data": None}
    assert response.headers["X-Request-Id"]


@pytest.mark.asyncio
async def test_liveness_exposes_stable_service_identity():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "automation-service"
    assert response.json()["check"] == "liveness"


@pytest.mark.asyncio
async def test_readiness_checks_database_without_exposing_failure_details(monkeypatch):
    main_module = importlib.import_module("app.main")

    class FailingConnection:
        async def __aenter__(self):
            raise RuntimeError("mysql://secret-user:secret-password@private-host/database")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FailingEngine:
        def connect(self):
            return FailingConnection()

    async def writable(_base_dir):
        return None

    monkeypatch.setattr(main_module, "engine", FailingEngine())
    monkeypatch.setattr(main_module, "probe_upload_storage", writable)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "service": "automation-service",
        "dependencies": {"database": False, "uploadStorage": True},
    }
    assert "secret-password" not in response.text
