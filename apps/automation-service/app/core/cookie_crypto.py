"""Cookie encryption/decryption helpers shared with Java core-api.

Storage format: enc:v1:{base64url(iv)}:{base64url(cipher_text_with_tag)}
Legacy plaintext values are returned as-is for backward compatibility.
"""
from __future__ import annotations

import base64
import hashlib
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import settings

PREFIX = "enc:v1:"
DEV_SECRET = "dev-only-cookie-crypto-secret-change-me-32-chars"


def _derive_key(secret: str) -> bytes:
    return hashlib.sha256((secret or DEV_SECRET).encode("utf-8")).digest()


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def encrypt_cookie_for_storage(cookie: Optional[str]) -> Optional[str]:
    if not cookie or cookie.startswith(PREFIX):
        return cookie
    key = _derive_key(getattr(settings, "cookie_crypto_secret", DEV_SECRET))
    iv = os.urandom(12)
    cipher = AESGCM(key).encrypt(iv, cookie.encode("utf-8"), None)
    return f"{PREFIX}{_b64e(iv)}:{_b64e(cipher)}"


def decrypt_cookie_if_needed(stored: Optional[str]) -> Optional[str]:
    if not stored or not stored.startswith(PREFIX):
        return stored
    try:
        _, _, iv_b64, cipher_b64 = stored.split(":", 3)
        key = _derive_key(getattr(settings, "cookie_crypto_secret", DEV_SECRET))
        plain = AESGCM(key).decrypt(_b64d(iv_b64), _b64d(cipher_b64), None)
        return plain.decode("utf-8")
    except Exception as exc:
        raise RuntimeError("Cookie 解密失败，请检查 COOKIE_CRYPTO_SECRET 是否与 core-api 一致") from exc
