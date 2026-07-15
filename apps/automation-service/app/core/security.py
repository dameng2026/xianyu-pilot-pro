import bcrypt
import jwt
from datetime import datetime, timedelta
from .config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_token(user_id: int, username: str, tenant_id: int, security_version: int) -> str:
    if int(security_version) <= 0:
        raise ValueError("security_version must be positive")
    payload = {
        "user_id": user_id,
        "username": username,
        "tenant_id": tenant_id,
        "tokenType": "user",
        "authVersion": int(security_version),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "exp": datetime.utcnow() + timedelta(milliseconds=settings.jwt_expiration_ms),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """解码 JWT。

    兼容两种 token：
    1. Python automation-service 自己签发的 token
       claims: user_id, username, tenant_id
       secret: settings.jwt_secret
    2. Java core-api 签发的前端登录 token
       claims: sub, userName, tenantId
       secret: settings.admin_jwt_secret（对应 core-api 的 admin.jwt.secret）
    """
    errors = []

    # 先尝试 Python 自己的 token
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["exp", "iat", "iss", "aud", "user_id", "username", "tenant_id", "tokenType", "authVersion"]},
        )
        if payload.get("tokenType") != "user":
            raise jwt.InvalidTokenError("wrong token type")
        try:
            if int(payload.get("authVersion")) <= 0:
                raise ValueError
        except (TypeError, ValueError):
            raise jwt.InvalidTokenError("invalid auth version")
        return payload
    except Exception as e:
        errors.append(f"python-jwt: {e}")

    # 再尝试 Java core-api 的 token
    try:
        payload = jwt.decode(
            token,
            settings.admin_jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.admin_jwt_issuer,
            audience=settings.admin_jwt_audience,
            options={"require": ["exp", "iat", "iss", "aud", "sub", "userName", "tenantId", "tokenType", "authVersion"]},
        )
        if payload.get("tokenType") != "user":
            raise jwt.InvalidTokenError("wrong token type")
        try:
            if int(payload.get("authVersion")) <= 0:
                raise ValueError
        except (TypeError, ValueError):
            raise jwt.InvalidTokenError("invalid auth version")
        # 标准化字段，兼容现有依赖 user_id / username / tenant_id 的代码
        normalized = dict(payload)
        if "user_id" not in normalized and payload.get("sub") is not None:
            try:
                normalized["user_id"] = int(payload.get("sub"))
            except (TypeError, ValueError):
                normalized["user_id"] = payload.get("sub")
        if "username" not in normalized and payload.get("userName") is not None:
            normalized["username"] = payload.get("userName")
        if "tenant_id" not in normalized and payload.get("tenantId") is not None:
            try:
                normalized["tenant_id"] = int(payload.get("tenantId"))
            except (TypeError, ValueError):
                normalized["tenant_id"] = payload.get("tenantId")
        return normalized
    except Exception as e:
        errors.append(f"java-jwt: {e}")

    raise jwt.InvalidTokenError("; ".join(errors))
