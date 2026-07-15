import asyncio
import io
import threading
import time
from contextlib import asynccontextmanager

import pytest
from PIL import Image

from app.api.v1.routes import auto_category
from app.core.image_security import MAX_IMAGE_BYTES


def _png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 6), (20, 40, 60)).save(output, format="PNG")
    return output.getvalue()


class _Socket:
    def __init__(self, address: str):
        self.address = address

    def getpeername(self):
        return (self.address, 443)


class _Connection:
    def __init__(self, address: str):
        self.sock = _Socket(address)


class _Raw:
    def __init__(self, address: str):
        self._connection = _Connection(address)


class _Response:
    status_code = 200

    def __init__(self, content: bytes, *, content_type="image/png", address="8.8.8.8"):
        self.content = content
        self.headers = {"content-type": content_type, "content-length": str(len(content))}
        self.raw = _Raw(address)
        self.closed = False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        return iter((self.content,))

    def close(self):
        self.closed = True


class _MappingResult:
    def __init__(self, row):
        self.row = row

    def mappings(self):
        return self

    def first(self):
        return self.row


def test_remote_category_image_rejects_private_connected_peer(monkeypatch):
    response = _Response(_png_bytes(), address="169.254.169.254")
    monkeypatch.setattr(
        auto_category.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("8.8.8.8", 443))],
    )
    monkeypatch.setattr(auto_category.requests, "get", lambda *_args, **_kwargs: response)

    with pytest.raises(ValueError, match="连接到了非公网地址"):
        auto_category._resolve_image_data("https://images.example/cover.png", tenant_id=7)
    assert response.closed


def test_remote_category_image_validates_magic_and_declared_type():
    response = _Response(b"<html>not an image</html>", content_type="image/png")

    with pytest.raises(ValueError):
        auto_category._read_limited_image_response(response)


def test_remote_category_image_uses_five_megabyte_limit():
    response = _Response(_png_bytes())
    response.headers["content-length"] = str(MAX_IMAGE_BYTES + 1)

    with pytest.raises(ValueError, match="5MB"):
        auto_category._read_limited_image_response(response)


def test_local_category_image_is_revalidated_after_storage(monkeypatch, tmp_path):
    tenant_dir = tmp_path / "tenant-7"
    tenant_dir.mkdir()
    (tenant_dir / "cover.png").write_bytes(b"not an image")
    monkeypatch.setattr(auto_category, "_UPLOAD_BASE_DIR", str(tmp_path))

    with pytest.raises(ValueError):
        auto_category._resolve_image_data(
            "/uploads/images/tenant-7/cover.png", tenant_id=7
        )


def test_tenant_cache_image_is_read_from_shared_storage_without_http_fallback(monkeypatch, tmp_path):
    images_root = tmp_path / "images"
    cache_root = tmp_path / "cache" / "tenant-7"
    images_root.mkdir()
    cache_root.mkdir(parents=True)
    content = _png_bytes()
    (cache_root / "generated.png").write_bytes(content)
    monkeypatch.setattr(auto_category, "_UPLOAD_BASE_DIR", str(images_root))
    monkeypatch.setattr(
        auto_category.requests,
        "get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("governed local media must not use unauthenticated HTTP fallback")
        ),
    )

    assert auto_category._resolve_image_data(
        "/uploads/cache/tenant-7/generated.png", tenant_id=7
    ) == content


@pytest.mark.asyncio
async def test_blocking_category_work_runs_off_event_loop_thread(monkeypatch):
    monkeypatch.setattr(auto_category, "_auto_category_semaphore", asyncio.Semaphore(1))
    event_loop_thread = threading.get_ident()

    worker_thread = await auto_category._bounded_blocking_call(
        threading.get_ident, timeout=1
    )

    assert worker_thread != event_loop_thread


@pytest.mark.asyncio
async def test_category_timeout_keeps_concurrency_slot_until_worker_finishes(monkeypatch):
    monkeypatch.setattr(auto_category, "_auto_category_semaphore", asyncio.Semaphore(1))

    def slow_operation():
        time.sleep(0.06)
        return "done"

    with pytest.raises(auto_category.AutoCategoryTimeoutError):
        await auto_category._bounded_blocking_call(
            slow_operation, timeout=0.01
        )

    assert auto_category._auto_category_semaphore.locked()
    await asyncio.sleep(0.08)
    assert not auto_category._auto_category_semaphore.locked()


@pytest.mark.asyncio
async def test_url_category_route_uses_transient_upload_governance(monkeypatch):
    image = _png_bytes()
    events = []

    async def account_cookie(*_args, **_kwargs):
        return "unb=1; _m_h5_tk=token_1"

    @asynccontextmanager
    async def governed(content, **kwargs):
        events.append(("enter", content, kwargs))
        yield 123
        events.append(("exit", content, kwargs))

    monkeypatch.setattr(auto_category, "_get_account_cookie", account_cookie)
    monkeypatch.setattr(auto_category, "_resolve_image_data", lambda *_args: image)
    monkeypatch.setattr(auto_category, "govern_transient_upload", governed)
    monkeypatch.setattr(
        auto_category,
        "auto_category_service",
        lambda **_kwargs: {"success": True, "fallbackRequired": False},
    )
    monkeypatch.setattr(auto_category, "_auto_category_semaphore", asyncio.Semaphore(2))

    result = await auto_category.auto_category(
        account_id=9,
        body={"coverImageUrl": "https://images.example/cover.png"},
        db=object(),
        current_user={"tenant_id": 7, "user_id": 11},
    )

    assert result.code == 200
    assert result.data["success"] is True
    assert [event[0] for event in events] == ["enter", "exit"]
    assert events[0][2] == {
        "tenant_id": 7,
        "user_id": 11,
        "source_type": "auto-category-url",
    }


@pytest.mark.asyncio
async def test_url_category_timeout_returns_truthful_fallback_state(monkeypatch):
    image = _png_bytes()

    async def account_cookie(*_args, **_kwargs):
        return "unb=1; _m_h5_tk=token_1"

    calls = 0

    async def bounded(function, *_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return image
        raise auto_category.AutoCategoryTimeoutError()

    @asynccontextmanager
    async def governed(*_args, **_kwargs):
        yield 123

    monkeypatch.setattr(auto_category, "_get_account_cookie", account_cookie)
    monkeypatch.setattr(auto_category, "_bounded_blocking_call", bounded)
    monkeypatch.setattr(auto_category, "govern_transient_upload", governed)

    result = await auto_category.auto_category(
        account_id=9,
        body={"coverImageUrl": "https://images.example/cover.png"},
        db=object(),
        current_user={"tenant_id": 7, "user_id": 11},
    )

    assert result.code == 200
    assert result.data["success"] is False
    assert result.data["fallbackRequired"] is True
    assert result.data["fallbackReason"] == "SERVICE_TIMEOUT"


@pytest.mark.asyncio
async def test_local_category_url_requires_active_matching_storage_asset():
    content = _png_bytes()

    class _AssetDb:
        async def execute(self, _statement, params):
            assert params == {
                "tenant_id": 7,
                "storage_key": "tenant-7/cover.png",
                "public_url": "/uploads/images/tenant-7/cover.png",
            }
            import hashlib
            return _MappingResult({
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            })

    await auto_category._verify_active_local_image_asset(
        _AssetDb(), "/uploads/images/tenant-7/cover.png", 7, content
    )


@pytest.mark.asyncio
async def test_local_cache_url_requires_active_matching_storage_asset():
    content = _png_bytes()

    class _AssetDb:
        async def execute(self, _statement, params):
            assert params == {
                "tenant_id": 7,
                "storage_key": "cache/tenant-7/generated.png",
                "public_url": "/uploads/cache/tenant-7/generated.png",
            }
            import hashlib
            return _MappingResult({
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            })

    await auto_category._verify_active_local_image_asset(
        _AssetDb(), "/uploads/cache/tenant-7/generated.png", 7, content
    )


@pytest.mark.asyncio
async def test_local_category_url_rejects_missing_or_tampered_storage_asset():
    content = _png_bytes()

    class _MissingDb:
        async def execute(self, *_args, **_kwargs):
            return _MappingResult(None)

    with pytest.raises(ValueError, match="unavailable"):
        await auto_category._verify_active_local_image_asset(
            _MissingDb(), "/uploads/images/tenant-7/cover.png", 7, content
        )

    class _TamperedDb:
        async def execute(self, *_args, **_kwargs):
            return _MappingResult({
                "size_bytes": len(content),
                "sha256": "0" * 64,
            })

    with pytest.raises(ValueError, match="storage record"):
        await auto_category._verify_active_local_image_asset(
            _TamperedDb(), "/uploads/images/tenant-7/cover.png", 7, content
        )
