import json

from app.api.v1.routes.feishu import _match_feishu_tenant
from app.services.feishu_bot import _decrypt_secret, _encrypt_secret


def _row(tenant_id: int, app_id: str, tenant_key: str = "") -> dict:
    return {
        "tenant_id": tenant_id,
        "config_json": json.dumps({
            "channels": [{
                "type": "feishu_app",
                "enabled": True,
                "appId": app_id,
                "tenantKey": tenant_key,
            }]
        }),
    }


def test_each_feishu_app_id_maps_to_exactly_one_tenant():
    rows = [_row(11, "app-a", "tenant-a"), _row(22, "app-b", "tenant-b")]

    assert _match_feishu_tenant(rows, tenant_key="tenant-a", app_id="app-a") == 11
    assert _match_feishu_tenant(rows, tenant_key="tenant-b", app_id="app-b") == 22
    assert _match_feishu_tenant(rows, tenant_key="unknown", app_id="unknown") is None


def test_feishu_mapping_never_falls_back_to_the_only_configured_tenant():
    rows = [_row(11, "app-a", "tenant-a")]

    assert _match_feishu_tenant(rows, tenant_key="", app_id="") is None
    assert _match_feishu_tenant(rows, tenant_key="unknown", app_id="unknown") is None


def test_duplicate_feishu_app_binding_is_rejected():
    rows = [_row(11, "duplicate"), _row(22, "duplicate")]

    assert _match_feishu_tenant(rows, tenant_key="", app_id="duplicate") is None


def test_feishu_secrets_use_the_shared_encrypted_storage_envelope():
    encrypted = _encrypt_secret("plain-app-secret")

    assert encrypted.startswith("enc:v1:")
    assert "plain-app-secret" not in encrypted
    assert _decrypt_secret(encrypted) == "plain-app-secret"
