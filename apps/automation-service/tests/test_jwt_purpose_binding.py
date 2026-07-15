from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException

from app.api.v1.deps import get_current_user, get_internal_service_identity
from app.core.config import settings
from app.core.security import decode_token


def _java_token(*, token_type="user", tenant_id=9, issuer=None, audience=None, auth_version=3):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "iss": issuer or settings.admin_jwt_issuer,
            "aud": audience or settings.admin_jwt_audience,
            "sub": "7",
            "userName": "tenant-user",
            "tenantId": str(tenant_id),
            "tokenType": token_type,
            "authVersion": auth_version,
            "iat": now,
            "exp": now + timedelta(minutes=10),
        },
        settings.admin_jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def test_python_accepts_only_purpose_bound_java_user_tokens():
    payload = decode_token(_java_token())

    assert payload["user_id"] == 7
    assert payload["tenant_id"] == 9


@pytest.mark.parametrize(
    "token",
    [
        _java_token(token_type="admin"),
        _java_token(issuer="attacker-issuer"),
        _java_token(audience="another-service"),
    ],
)
def test_python_rejects_admin_wrong_issuer_and_wrong_audience_tokens(token):
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token)


class _Result:
    def __init__(self, user):
        self.user = user

    def scalar_one_or_none(self):
        return self.user


class _Db:
    async def execute(self, _query):
        return _Result(SimpleNamespace(id=7, tenant_id=10, username="wrong-tenant", security_version=3))


@pytest.mark.asyncio
async def test_authenticated_user_must_belong_to_claimed_tenant():
    with pytest.raises(HTTPException) as error:
        await get_current_user(
            authorization=f"Bearer {_java_token(tenant_id=9)}",
            x_internal_token=None,
            x_internal_tenant_id=None,
            db=_Db(),
        )

    assert error.value.status_code == 401


class _AuthoritativeDb:
    def __init__(self, *, username="tenant-user", security_version=3, error=None):
        self.username = username
        self.security_version = security_version
        self.error = error

    async def execute(self, _query):
        if self.error:
            raise self.error
        return _Result(
            SimpleNamespace(
                id=7,
                tenant_id=9,
                username=self.username,
                security_version=self.security_version,
            )
        )


@pytest.mark.asyncio
async def test_security_version_change_immediately_revokes_automation_access():
    with pytest.raises(HTTPException) as error:
        await get_current_user(
            authorization=f"Bearer {_java_token(auth_version=3)}",
            x_internal_token=None,
            x_internal_tenant_id=None,
            db=_AuthoritativeDb(security_version=4),
        )

    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_username_change_immediately_revokes_old_automation_token():
    with pytest.raises(HTTPException) as error:
        await get_current_user(
            authorization=f"Bearer {_java_token()}",
            x_internal_token=None,
            x_internal_tenant_id=None,
            db=_AuthoritativeDb(username="renamed-user"),
        )

    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_authoritative_auth_state_failure_is_explicitly_unavailable():
    with pytest.raises(HTTPException) as error:
        await get_current_user(
            authorization=f"Bearer {_java_token()}",
            x_internal_token=None,
            x_internal_tenant_id=None,
            db=_AuthoritativeDb(error=RuntimeError("db unavailable")),
        )

    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_authenticated_identity_records_browser_auth_type():
    identity = await get_current_user(
        authorization=f"Bearer {_java_token()}",
        x_internal_token=None,
        x_internal_tenant_id=None,
        db=_AuthoritativeDb(),
    )

    assert identity["auth_type"] == "user"


@pytest.mark.asyncio
async def test_internal_only_dependency_rejects_browser_identity():
    with pytest.raises(HTTPException) as error:
        await get_internal_service_identity(
            current_user={"tenant_id": 9, "user_id": 7, "auth_type": "user"}
        )

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_internal_only_dependency_accepts_gateway_identity():
    identity = {"tenant_id": 9, "user_id": 0, "auth_type": "internal"}

    assert await get_internal_service_identity(current_user=identity) is identity


def test_java_user_token_without_auth_version_is_rejected():
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "iss": settings.admin_jwt_issuer,
            "aud": settings.admin_jwt_audience,
            "sub": "7",
            "userName": "tenant-user",
            "tenantId": "9",
            "tokenType": "user",
            "iat": now,
            "exp": now + timedelta(minutes=10),
        },
        settings.admin_jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token)
