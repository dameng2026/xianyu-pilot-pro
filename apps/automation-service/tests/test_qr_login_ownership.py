import re
import time

import pytest

from app.api.v1.routes import internal, misc
from app.core import xianyu_qr_login as qr
from app.main import app


VALID_SESSION = "A" * 43
OTHER_SESSION = "B" * 43


@pytest.fixture(autouse=True)
def clear_qr_sessions():
    with qr._lock:
        qr._sessions.clear()
    yield
    with qr._lock:
        qr._sessions.clear()


def _stored_session(user_id: int, tenant_id: int) -> dict:
    return {
        "session": object(),
        "login_form": {},
        "qr_image": "data:image/png;base64,AA==",
        "status": "new",
        "created_at": time.time(),
        "user_id": user_id,
        "tenant_id": tenant_id,
    }


def test_generate_requires_positive_owner_before_contacting_provider(monkeypatch):
    monkeypatch.setattr(
        qr,
        "_get_m_h5_tk",
        lambda _session: pytest.fail("provider must not be called without an owner"),
    )

    with pytest.raises(ValueError):
        qr.generate_qrcode(user_id=None, tenant_id=1)
    with pytest.raises(ValueError):
        qr.generate_qrcode(user_id=1, tenant_id=0)


def test_generate_uses_high_entropy_url_safe_session_ids(monkeypatch):
    monkeypatch.setattr(qr, "_get_m_h5_tk", lambda _session: "token")
    monkeypatch.setattr(qr, "_get_login_params", lambda _session: {"ck": "test"})
    monkeypatch.setattr(
        qr,
        "_generate_qrcode",
        lambda _session, _form: "data:image/png;base64,AA==",
    )

    first = qr.generate_qrcode(user_id=7, tenant_id=9)["sessionId"]
    second = qr.generate_qrcode(user_id=7, tenant_id=9)["sessionId"]

    assert first != second
    assert re.fullmatch(r"[A-Za-z0-9_-]{32,64}", first)
    assert qr.get_session_context(first)["user_id"] == 7
    assert qr.get_session_context(first)["tenant_id"] == 9


def test_generate_rejects_owner_session_overflow_before_contacting_provider(monkeypatch):
    with qr._lock:
        for index in range(qr._MAX_SESSIONS_PER_OWNER):
            qr._sessions[f"owner-session-{index}"] = _stored_session(user_id=7, tenant_id=9)

    monkeypatch.setattr(
        qr,
        "_get_m_h5_tk",
        lambda _session: pytest.fail("provider must not be called after the owner limit"),
    )

    with pytest.raises(RuntimeError):
        qr.generate_qrcode(user_id=7, tenant_id=9)


def test_failed_generation_releases_reserved_session(monkeypatch):
    monkeypatch.setattr(qr, "_get_m_h5_tk", lambda _session: "token")
    monkeypatch.setattr(
        qr,
        "_get_login_params",
        lambda _session: (_ for _ in ()).throw(RuntimeError("provider failed")),
    )

    with pytest.raises(RuntimeError):
        qr.generate_qrcode(user_id=7, tenant_id=9)

    with qr._lock:
        assert qr._sessions == {}


def test_owner_cleanup_never_removes_another_tenants_sessions():
    with qr._lock:
        qr._sessions[VALID_SESSION] = _stored_session(user_id=7, tenant_id=9)
        qr._sessions[OTHER_SESSION] = _stored_session(user_id=7, tenant_id=10)

    assert qr.cleanup_session_for_owner(VALID_SESSION, user_id=7, tenant_id=10) is False
    assert qr.cleanup_sessions_for_owner(user_id=7, tenant_id=9) == 1
    assert qr.get_session_context(VALID_SESSION) is None
    assert qr.get_session_context(OTHER_SESSION) is not None


@pytest.mark.asyncio
async def test_internal_status_requires_exact_session_owner(monkeypatch):
    monkeypatch.setattr(
        qr,
        "get_session_context",
        lambda _session_id: {"user_id": 7, "tenant_id": 9, "status": "new"},
    )
    monkeypatch.setattr(
        qr,
        "get_session_status",
        lambda _session_id: pytest.fail("cross-tenant request must not poll provider"),
    )

    missing = await internal.internal_qrlogin_status(
        VALID_SESSION,
        body={"tenantId": 9},
        db=None,
        _=None,
    )
    wrong_tenant = await internal.internal_qrlogin_status(
        VALID_SESSION,
        body={"userId": 7, "tenantId": 10},
        db=None,
        _=None,
    )

    assert missing.code == 400
    assert wrong_tenant.code == 403


@pytest.mark.asyncio
async def test_direct_status_requires_exact_authenticated_owner(monkeypatch):
    monkeypatch.setattr(
        misc,
        "get_session_context",
        lambda _session_id: {"user_id": 7, "tenant_id": 9, "status": "new"},
    )
    monkeypatch.setattr(
        misc,
        "get_session_status",
        lambda _session_id: pytest.fail("cross-tenant request must not poll provider"),
    )

    result = await misc.qrlogin_status(
        VALID_SESSION,
        db=None,
        current_user={"user_id": 7, "tenant_id": 10},
    )

    assert result.code == 403


def test_browser_facing_automation_api_has_no_cookie_export_route():
    routes = {
        (route.path, method)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }

    assert ("/api/qrlogin/cookies/{session_id}", "POST") not in routes
    assert ("/api/internal/qrlogin/cookies/{session_id}", "POST") in routes
    assert ("/api/internal/qrlogin/cookies/{session_id}", "GET") not in routes
