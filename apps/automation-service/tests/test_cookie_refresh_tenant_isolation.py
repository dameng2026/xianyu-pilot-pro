from pathlib import Path

import pytest

from app.api.v1.routes import account
from app.main import app
from app.services import cookie_token_refresher


@pytest.mark.asyncio
async def test_force_refresh_route_uses_only_authenticated_tenant(monkeypatch):
    captured = []

    class _OwnedResult:
        def scalar_one_or_none(self):
            return 8

    class _OwnedDb:
        async def execute(self, _statement):
            return _OwnedResult()

    async def capture(account_id, tenant_id, refresh_type):
        captured.append((account_id, tenant_id, refresh_type))
        return {"success": True, "details": {"cookie": "ok"}}

    monkeypatch.setattr(cookie_token_refresher, "force_refresh_account", capture)

    result = await account.force_refresh_account(
        data={"accountId": 8, "tenantId": 999, "refreshType": "cookie"},
        db=_OwnedDb(),
        current_user={"user_id": 7, "tenant_id": 42},
    )

    assert result.code == 200
    assert captured == [(8, 42, "cookie")]


@pytest.mark.asyncio
async def test_force_refresh_rejects_cached_state_from_another_tenant(monkeypatch):
    monkeypatch.setattr(
        cookie_token_refresher,
        "_states",
        {
            8: cookie_token_refresher.AccountRefreshState(
                account_id=8,
                tenant_id=99,
            )
        },
    )

    result = await cookie_token_refresher.force_refresh_account(
        account_id=8,
        tenant_id=42,
        refresh_type="cookie",
    )

    assert result["success"] is False
    assert result["errorCode"] == "ACCOUNT_NOT_FOUND"


@pytest.mark.asyncio
async def test_force_refresh_route_rejects_account_not_owned_by_user(monkeypatch):
    class _MissingResult:
        def scalar_one_or_none(self):
            return None

    class _MissingDb:
        async def execute(self, _statement):
            return _MissingResult()

    async def _must_not_refresh(*_args, **_kwargs):
        pytest.fail("another user's account must not be refreshed")

    monkeypatch.setattr(cookie_token_refresher, "force_refresh_account", _must_not_refresh)

    result = await account.force_refresh_account(
        data={"accountId": 8, "refreshType": "cookie"},
        db=_MissingDb(),
        current_user={"user_id": 7, "tenant_id": 42},
    )

    assert result.code == 404


def test_user_api_cannot_start_or_stop_the_global_dispatcher():
    routes = {
        (route.path, method)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }

    assert ("/api/account/refresh/start", "POST") not in routes
    assert ("/api/account/refresh/stop", "POST") not in routes


def test_force_refresh_database_lookup_is_tenant_scoped():
    source = Path(cookie_token_refresher.__file__).read_text(encoding="utf-8")

    assert "WHERE a.id = :aid AND a.tenant_id = :tid AND a.deleted = 0" in source
