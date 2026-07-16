import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _production_settings(**overrides):
    values = {
        "app_env": "production",
        "internal_api_token": "i" * 48,
        "admin_jwt_secret": "a" * 48,
        "cookie_crypto_secret": "c" * 48,
        "jwt_secret": "j" * 48,
        "mysql_password": "database-password-with-32-characters",
        "cors_allowed_origins": "https://app.example.com",
        "upload_governance_enabled": True,
        "upload_tenant_quota_bytes": 104857600,
        "upload_global_quota_bytes": 10737418240,
        "upload_rate_limit_requests": 30,
        "upload_rate_limit_window_seconds": 60,
        "upload_max_concurrent_per_tenant": 2,
        "upload_max_concurrent_global": 8,
        "upload_retention_days": 365,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_rejects_default_python_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        _production_settings(
            jwt_secret="xianyu-assistant-jwt-secret-key-2026-04-22-very-long-secret-for-hmac-sha"
        )


def test_production_rejects_default_database_password():
    with pytest.raises(ValidationError, match="MYSQL_PASSWORD"):
        _production_settings(mysql_password="xianyu_pass")


def test_unknown_environment_name_fails_closed_as_production_like():
    with pytest.raises(ValidationError):
        _production_settings(
            app_env="prodcution",
            internal_api_token="dev-only-internal-api-token-change-me-32-chars",
        )


def test_enabled_ai_provider_requires_complete_configuration():
    with pytest.raises(ValidationError, match="AI_PROVIDER"):
        _production_settings(ai_provider_enabled=True, ai_provider_api_key="", ai_provider_base_url="")


@pytest.mark.parametrize(
    "origin",
    ["*", "http://app.example.com", "javascript:alert(1)"],
)
def test_production_rejects_unsafe_cors_origins(origin):
    with pytest.raises(ValidationError, match="CORS_ALLOWED_ORIGINS"):
        _production_settings(cors_allowed_origins=origin)


def test_production_accepts_explicit_strong_configuration():
    settings = _production_settings(
        ai_provider_enabled=True,
        ai_provider_api_key="provider-secret",
        ai_provider_base_url="https://ai.example.com/v1",
    )

    assert settings.app_env == "production"


def test_production_rejects_unmetered_or_implicit_upload_governance():
    with pytest.raises(ValidationError, match="UPLOAD_GOVERNANCE_ENABLED"):
        _production_settings(upload_governance_enabled=False)
    with pytest.raises(ValidationError, match="upload governance limits"):
        _production_settings(upload_rate_limit_requests=None)


def test_production_accepts_optional_storage_quota_fields():
    """存储配额字段（tenant / global）已不再用于 enforcement，可省略。"""
    settings = _production_settings(
        upload_tenant_quota_bytes=None,
        upload_global_quota_bytes=None,
    )
    assert settings.app_env == "production"


def test_runtime_schema_mutations_default_off_in_production_and_on_in_development():
    assert _production_settings().runtime_schema_mutations_allowed is False
    assert Settings(_env_file=None, app_env="development").runtime_schema_mutations_allowed is True


def test_runtime_schema_mutation_override_is_explicit():
    with pytest.raises(ValidationError, match="SCHEMA_RUNTIME_MUTATIONS_ENABLED"):
        _production_settings(schema_runtime_mutations_enabled=True)
    assert Settings(
        _env_file=None,
        app_env="development",
        schema_runtime_mutations_enabled=False,
    ).runtime_schema_mutations_allowed is False
