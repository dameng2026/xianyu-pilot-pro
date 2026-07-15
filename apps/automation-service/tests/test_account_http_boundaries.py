from __future__ import annotations

import pytest
from sqlalchemy import and_

from app.api.v1.routes import account
from app.models.entities import XianyuAccount
from app.schemas.account import AccountReqDTO
from app.services import cookie_token_refresher


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _CreateAccountDb:
    def __init__(self):
        self.added = []
        self.flushes = 0
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, _statement, _params=None):
        return _ScalarResult(None)

    def add(self, entity):
        self.added.append(entity)

    async def flush(self):
        self.flushes += 1
        created = next(entity for entity in self.added if isinstance(entity, XianyuAccount))
        created.id = 123

    async def refresh(self, _entity):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_account_creation_commits_account_credentials_and_runtime_atomically():
    db = _CreateAccountDb()

    result = await account.add_account(
        AccountReqDTO(cookie="unb=buyer-1; _m_h5_tk=token-1;"),
        db=db,
        current_user={"tenant_id": 7, "user_id": 9},
    )

    assert result.code == 200
    assert result.data.account_id == 123
    assert db.flushes == 1
    assert db.commits == 1
    assert len(db.added) == 3


def test_account_access_scope_includes_tenant_user_and_shared_accounts():
    sql = str(and_(*account._account_access_conditions({"tenant_id": 4, "user_id": 5})))

    assert "xianyu_account.tenant_id" in sql
    assert "xianyu_account.user_id" in sql
    assert "IS NULL" in sql


def test_unb_cookie_parser_accepts_standard_semicolon_variants():
    assert account.extract_unb_from_cookie("foo=1;unb=buyer-1;bar=2") == "buyer-1"
    assert account.extract_unb_from_cookie("foo=1; unb=buyer-2; bar=2") == "buyer-2"


@pytest.mark.asyncio
async def test_refresh_status_filters_other_tenants_and_redacts_runtime_error(monkeypatch):
    class _AllowedAccountsResult:
        def scalars(self):
            return self

        def all(self):
            return [1]

    class _AllowedAccountsDb:
        async def execute(self, _statement):
            return _AllowedAccountsResult()

    async def _status():
        return {
            "running": True,
            "accountsCount": 2,
            "config": {"cookieKeepaliveIntervalMinutes": 30},
            "accounts": [
                {
                    "accountId": 1,
                    "tenantId": 10,
                    "lastCookieKeepaliveOk": False,
                    "lastMh5tkRefreshOk": False,
                    "lastWsTokenRefreshOk": False,
                    "lastError": "Authorization=secret-token provider response body",
                },
                {"accountId": 2, "tenantId": 20, "lastError": "another tenant secret"},
            ],
        }

    monkeypatch.setattr(cookie_token_refresher, "get_dispatcher_status", _status)

    result = await account.get_refresh_status(
        db=_AllowedAccountsDb(),
        current_user={"tenant_id": 10, "user_id": 30},
    )

    assert result.code == 200
    assert result.data["accountsCount"] == 1
    assert [entry["accountId"] for entry in result.data["accounts"]] == [1]
    serialized = str(result.data)
    assert "secret-token" not in serialized
    assert "another tenant" not in serialized


@pytest.mark.asyncio
async def test_failed_force_refresh_is_not_reported_as_success_or_echoed(monkeypatch):
    class _OwnedDb:
        async def execute(self, _statement):
            return _ScalarResult(8)

    async def _fail(*_args, **_kwargs):
        return {
            "success": False,
            "errorCode": "REFRESH_UNAVAILABLE",
            "error": "provider response Authorization=secret-token",
            "last_error": "database details",
            "details": {"cookie": "failed"},
        }

    monkeypatch.setattr(cookie_token_refresher, "force_refresh_account", _fail)

    result = await account.force_refresh_account(
        data={"accountId": 8, "refreshType": "cookie"},
        db=_OwnedDb(),
        current_user={"tenant_id": 10},
    )

    assert result.code == 409
    assert result.data == {"success": False, "details": {"cookie": "failed"}}
    assert "secret-token" not in result.msg
    assert "database" not in str(result.data)
