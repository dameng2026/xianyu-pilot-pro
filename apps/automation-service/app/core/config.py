from pathlib import Path as _Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import Optional
from urllib.parse import urlparse


_DEVELOPMENT_ENVS = {"dev", "development", "test", "testing", "local"}


def is_production_like(environment: str | None) -> bool:
    return str(environment or "dev").strip().lower() not in _DEVELOPMENT_ENVS


def _find_env_file() -> str:
    """从当前文件位置向上查找 .env 文件。

    config.py 位于 apps/automation-service/app/core/config.py，
    项目根目录的 .env 在向上 4 级。但无论从哪个工作目录启动 Python
    （如 cd apps/automation-service; python run.py），都需要加载
    项目根目录的 .env，否则 ADMIN_JWT_SECRET / COOKIE_CRYPTO_SECRET
    等关键配置会使用默认值，与 Java core-api 不一致。
    """
    current = _Path(__file__).resolve().parent
    for _ in range(8):
        candidate = current / ".env"
        if candidate.exists():
            return str(candidate)
        current = current.parent
    return ".env"  # 兜底：让 pydantic 按原逻辑处理


class Settings(BaseSettings):
    app_name: str = "xianyu-assistant-python"
    server_port: int = 12401

    db_path: str = "../dbdata/xianyu_assistant.db"  # kept for backward compat

    # MySQL 配置（替换 SQLite）
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "xianyu"
    mysql_password: str = "xianyu_pass"
    mysql_database: str = "xianyu_assistant_admin"

    # Java core-api -> Python automation-service 内部调用令牌。Phase 1 起内部接口 fail-closed：为空时拒绝内部调用。
    internal_api_token: str = "dev-only-internal-api-token-change-me-32-chars"
    app_env: str = "dev"
    # None keeps local/test compatibility while production-like environments default fail-closed.
    # Production Compose pins this to false; a reviewed one-shot maintenance command may opt in.
    schema_runtime_mutations_enabled: Optional[bool] = None

    @property
    def runtime_schema_mutations_allowed(self) -> bool:
        if self.schema_runtime_mutations_enabled is not None:
            return self.schema_runtime_mutations_enabled
        return not is_production_like(self.app_env)

    # Python automation-service -> Java core-api 内部计费接口。Docker 中为 http://backend:18080。
    core_api_base_url: str = "http://localhost:18080"
    # Comma-separated browser origins allowed to call automation-service directly.
    # Leave empty when the service is only called by core-api on the internal Docker network.
    cors_allowed_origins: str = ""

    # Tenant-scoped upload governance.  Development receives conservative
    # defaults through the resolved_* properties.  Production-like
    # environments must explicitly opt in and set every bound, otherwise the
    # process refuses to start rather than accepting unmetered public uploads.
    upload_governance_enabled: Optional[bool] = None
    upload_tenant_quota_bytes: Optional[int] = None
    upload_global_quota_bytes: Optional[int] = None
    upload_rate_limit_requests: Optional[int] = None
    upload_rate_limit_window_seconds: Optional[int] = None
    upload_max_concurrent_per_tenant: Optional[int] = None
    upload_max_concurrent_global: Optional[int] = None
    upload_retention_days: Optional[int] = None

    @property
    def resolved_upload_governance_enabled(self) -> bool:
        return True if self.upload_governance_enabled is None else self.upload_governance_enabled

    @property
    def resolved_upload_tenant_quota_bytes(self) -> int:
        return 100 * 1024 * 1024 if self.upload_tenant_quota_bytes is None else self.upload_tenant_quota_bytes

    @property
    def resolved_upload_global_quota_bytes(self) -> int:
        return 10 * 1024 * 1024 * 1024 if self.upload_global_quota_bytes is None else self.upload_global_quota_bytes

    @property
    def resolved_upload_rate_limit_requests(self) -> int:
        return 30 if self.upload_rate_limit_requests is None else self.upload_rate_limit_requests

    @property
    def resolved_upload_rate_limit_window_seconds(self) -> int:
        return 60 if self.upload_rate_limit_window_seconds is None else self.upload_rate_limit_window_seconds

    @property
    def resolved_upload_max_concurrent_per_tenant(self) -> int:
        return 2 if self.upload_max_concurrent_per_tenant is None else self.upload_max_concurrent_per_tenant

    @property
    def resolved_upload_max_concurrent_global(self) -> int:
        return 8 if self.upload_max_concurrent_global is None else self.upload_max_concurrent_global

    @property
    def resolved_upload_retention_days(self) -> int:
        return 365 if self.upload_retention_days is None else self.upload_retention_days

    @property
    def mysql_url(self) -> str:
        return f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"

    @property
    def effective_internal_api_token(self) -> str:
        """返回内部服务令牌。

        本地开发中，某些 shell / IDE 会把 INTERNAL_API_TOKEN 设置为空字符串，
        这会覆盖 pydantic 的字段默认值，导致 Java -> Python 内部调用被拒绝。
        生产/预发仍由 validate_security_defaults 拦截弱令牌。
        """
        token = (self.internal_api_token or "").strip()
        return token or "dev-only-internal-api-token-change-me-32-chars"

    jwt_secret: str = "xianyu-assistant-jwt-secret-key-2026-04-22-very-long-secret-for-hmac-sha"
    jwt_expiration_ms: int = 2592000000
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "xianyu-automation-service"
    jwt_audience: str = "xianyu-automation-api"
    # 用于校验 core-api 签发给前端的登录 JWT；默认值需与 core-api 的 admin.jwt.secret 对齐。
    admin_jwt_secret: str = "please-change-this-admin-jwt-secret-at-least-32-chars"
    admin_jwt_issuer: str = "xianyu-core-api"
    admin_jwt_audience: str = "xianyu-user-api"
    notification_webhook_allowed_hosts: str = ""
    notification_smtp_allowed_hosts: str = ""
    cookie_crypto_secret: str = "dev-only-cookie-crypto-secret-change-me-32-chars"
    # Java 网关模式仅表示“前端/Java 通过 Python 网关访问消息能力”，
    # 不代表 Python 可以停止本地 WS 客户端。真实闲鱼 WS 连接仍由 Python 维护。
    use_java_message_gateway: bool = True

    # Phase3: OpenAI-compatible AI provider. 未配置时自动走本地启发式兜底。
    ai_provider_enabled: bool = False
    ai_provider_base_url: str = ""
    ai_provider_api_key: str = ""
    ai_provider_model: str = "gpt-4o-mini"
    ai_provider_timeout_seconds: int = 30

    # 闲鱼 MTOP 接口配置（自动分类）
    xianyu_mtop_app_key: str = "34839810"
    xianyu_mtop_category_api: str = "mtop.taobao.idle.kgraph.property.recommend"
    xianyu_mtop_category_version: str = "2.0"
    xianyu_mtop_upload_url: str = "https://stream-upload.goofish.com/api/upload.api?floderId=0&appkey=xy_chat"

    # 内容管理 JSON 文件存储目录
    STORAGE_DIR: str = "../data"

    # 自动分类置信度阈值
    # 注意：闲鱼官方 categoryPredictResult 已优先采用并跳过阈值检查，
    # 这里的阈值仅用于 score 排序回退场景。闲鱼实际返回的 score 普遍较低
    # （典型值 0.03~0.05），故降低阈值避免误判为低置信度。
    auto_category_min_score: float = 0.03
    auto_category_min_margin: float = 0.01


    @model_validator(mode="after")
    def validate_security_defaults(self):
        env = (self.app_env or "dev").strip().lower()
        prod_like = is_production_like(env)
        upload_values = {
            "UPLOAD_TENANT_QUOTA_BYTES": self.upload_tenant_quota_bytes,
            "UPLOAD_GLOBAL_QUOTA_BYTES": self.upload_global_quota_bytes,
            "UPLOAD_RATE_LIMIT_REQUESTS": self.upload_rate_limit_requests,
            "UPLOAD_RATE_LIMIT_WINDOW_SECONDS": self.upload_rate_limit_window_seconds,
            "UPLOAD_MAX_CONCURRENT_PER_TENANT": self.upload_max_concurrent_per_tenant,
            "UPLOAD_MAX_CONCURRENT_GLOBAL": self.upload_max_concurrent_global,
            "UPLOAD_RETENTION_DAYS": self.upload_retention_days,
        }
        if prod_like:
            if self.schema_runtime_mutations_enabled is True:
                raise ValueError("SCHEMA_RUNTIME_MUTATIONS_ENABLED must be false in prod/staging")
            if not (self.internal_api_token or "").strip():
                raise ValueError("INTERNAL_API_TOKEN must be configured in prod/staging")
            weak_values = {
                "please-change-this-admin-jwt-secret-at-least-32-chars",
                "dev-only-cookie-crypto-secret-change-me-32-chars",
                "xianyu-assistant-jwt-secret-key-2026-04-22-very-long-secret-for-hmac-sha",
                "dev-only-internal-api-token-change-me-32-chars",
            }
            if self.internal_api_token in weak_values or len(self.internal_api_token or "") < 32:
                raise ValueError("INTERNAL_API_TOKEN is unsafe in prod/staging")
            if self.admin_jwt_secret in weak_values or len(self.admin_jwt_secret or "") < 32:
                raise ValueError("ADMIN_JWT_SECRET is unsafe in prod/staging")
            if self.cookie_crypto_secret in weak_values or len(self.cookie_crypto_secret or "") < 32:
                raise ValueError("COOKIE_CRYPTO_SECRET is unsafe in prod/staging")
            if self.jwt_secret in weak_values or len(self.jwt_secret or "") < 32:
                raise ValueError("JWT_SECRET is unsafe in prod/staging")
            if self.jwt_algorithm != "HS256":
                raise ValueError("JWT_ALGORITHM must be HS256 in prod/staging")
            if self.mysql_password == "xianyu_pass" or len(self.mysql_password or "") < 16:
                raise ValueError("MYSQL_PASSWORD is unsafe in prod/staging")
            if self.upload_governance_enabled is not True:
                raise ValueError("UPLOAD_GOVERNANCE_ENABLED must be true in prod/staging")
            missing_upload_values = [name for name, value in upload_values.items() if value is None]
            if missing_upload_values:
                raise ValueError(
                    "upload governance limits must be explicit in prod/staging: "
                    + ", ".join(missing_upload_values)
                )

            origins = [item.strip() for item in (self.cors_allowed_origins or "").split(",") if item.strip()]
            for origin in origins:
                parsed = urlparse(origin)
                if origin == "*" or parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
                    raise ValueError("CORS_ALLOWED_ORIGINS must contain only explicit HTTPS origins in prod/staging")

            if self.ai_provider_enabled:
                provider_url = urlparse((self.ai_provider_base_url or "").strip())
                if not (self.ai_provider_api_key or "").strip() or provider_url.scheme != "https" or not provider_url.netloc:
                    raise ValueError("AI_PROVIDER requires an HTTPS base URL and API key when enabled")

        if not 5 * 1024 * 1024 <= self.resolved_upload_tenant_quota_bytes <= 1024 * 1024 * 1024 * 1024:
            raise ValueError("UPLOAD_TENANT_QUOTA_BYTES is outside the supported range")
        if not self.resolved_upload_tenant_quota_bytes <= self.resolved_upload_global_quota_bytes <= 10 * 1024 * 1024 * 1024 * 1024:
            raise ValueError("UPLOAD_GLOBAL_QUOTA_BYTES is outside the supported range")
        if not 1 <= self.resolved_upload_rate_limit_requests <= 10_000:
            raise ValueError("UPLOAD_RATE_LIMIT_REQUESTS is outside the supported range")
        if not 1 <= self.resolved_upload_rate_limit_window_seconds <= 3600:
            raise ValueError("UPLOAD_RATE_LIMIT_WINDOW_SECONDS is outside the supported range")
        if not 1 <= self.resolved_upload_max_concurrent_per_tenant <= 100:
            raise ValueError("UPLOAD_MAX_CONCURRENT_PER_TENANT is outside the supported range")
        if not self.resolved_upload_max_concurrent_per_tenant <= self.resolved_upload_max_concurrent_global <= 1000:
            raise ValueError("UPLOAD_MAX_CONCURRENT_GLOBAL is outside the supported range")
        if not 1 <= self.resolved_upload_retention_days <= 3650:
            raise ValueError("UPLOAD_RETENTION_DAYS is outside the supported range")
        return self

    model_config = SettingsConfigDict(env_file=_find_env_file(), env_file_encoding="utf-8", extra="ignore")


settings = Settings()
