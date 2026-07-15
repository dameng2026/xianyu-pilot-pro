from app.services import feishu_chat


def setup_function():
    feishu_chat._SESSIONS.clear()


def teardown_function():
    feishu_chat._SESSIONS.clear()


def test_feishu_session_cache_is_scoped_by_tenant_and_open_id():
    tenant_a = feishu_chat._get_session(11, "same-open-id")
    tenant_a.history.append({"role": "user", "content": "tenant-a-private-message"})
    tenant_a.state = "pending_qr_login"

    tenant_b = feishu_chat._get_session(22, "same-open-id")

    assert tenant_b is not tenant_a
    assert tenant_b.tenant_id == 22
    assert tenant_b.history == []
    assert tenant_b.state == "idle"
    assert set(feishu_chat._SESSIONS) == {
        (11, "same-open-id"),
        (22, "same-open-id"),
    }


def test_feishu_session_cache_rejects_missing_tenant_or_identity():
    for tenant_id, open_id in ((0, "open-id"), (-1, "open-id"), (11, "")):
        try:
            feishu_chat._get_session(tenant_id, open_id)
        except ValueError:
            continue
        raise AssertionError("invalid Feishu session identity must be rejected")
