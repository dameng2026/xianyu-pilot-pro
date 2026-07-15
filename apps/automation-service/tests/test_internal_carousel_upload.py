import io
from types import SimpleNamespace

import pytest
from PIL import Image
from starlette.datastructures import Headers, UploadFile

from app.api.v1.routes import internal


def _png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 6), (20, 40, 60)).save(output, format="PNG")
    return output.getvalue()


def _upload(content: bytes, content_type: str = "image/png") -> UploadFile:
    return UploadFile(
        filename="banner.png",
        file=io.BytesIO(content),
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.asyncio
async def test_internal_public_image_upload_publishes_only_governed_carousel_asset(monkeypatch):
    captured = {}

    async def store(image, **kwargs):
        captured.update(kwargs)
        captured["media_type"] = image.media_type
        return SimpleNamespace(
            public_url="/uploads/images/tenant-7/carousel_abcd1234.png", asset_id=91
        )

    monkeypatch.setattr(internal, "store_governed_image", store)

    result = await internal.internal_public_content_image_upload(
        _upload(_png_bytes()), "carousel", "7", None
    )

    assert result.code == 200
    assert result.data == {
        "url": "/uploads/images/tenant-7/carousel_abcd1234.png",
        "assetId": 91,
    }
    assert captured["tenant_id"] == 7
    assert captured["visibility"] == "public"
    assert captured["purpose"] == "carousel"
    assert captured["source_type"] == "carousel"
    assert captured["media_type"] == "image/png"


@pytest.mark.asyncio
async def test_internal_public_image_upload_rejects_invalid_tenant_before_storage(monkeypatch):
    async def unexpected_store(*_args, **_kwargs):
        raise AssertionError("storage must not be called")

    monkeypatch.setattr(internal, "store_governed_image", unexpected_store)

    result = await internal.internal_public_content_image_upload(
        _upload(_png_bytes()), "carousel", "0", None
    )

    assert result.code == 400
    assert result.data is None


@pytest.mark.asyncio
async def test_internal_public_image_upload_rejects_spoofed_image(monkeypatch):
    async def unexpected_store(*_args, **_kwargs):
        raise AssertionError("storage must not be called")

    monkeypatch.setattr(internal, "store_governed_image", unexpected_store)

    result = await internal.internal_public_content_image_upload(
        _upload(b"<script>alert(1)</script>"), "carousel", "7", None
    )

    assert result.code == 400
    assert result.data is None


@pytest.mark.asyncio
async def test_internal_public_image_upload_allows_open_source_content_purpose(monkeypatch):
    captured = {}

    async def store(_image, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            public_url="/uploads/images/tenant-7/open-content_abcd1234.png",
            asset_id=92,
        )

    monkeypatch.setattr(internal, "store_governed_image", store)

    result = await internal.internal_public_content_image_upload(
        _upload(_png_bytes()), "open-source-content", "7", None
    )

    assert result.code == 200
    assert captured["purpose"] == "open-source-content"
    assert captured["source_type"] == "open-source-content"
    assert captured["owner_type"] == "service"


@pytest.mark.asyncio
async def test_internal_public_image_upload_rejects_unapproved_purpose(monkeypatch):
    async def unexpected_store(*_args, **_kwargs):
        raise AssertionError("storage must not be called")

    monkeypatch.setattr(internal, "store_governed_image", unexpected_store)

    result = await internal.internal_public_content_image_upload(
        _upload(_png_bytes()), "avatar", "7", None
    )

    assert result.code == 400
    assert result.data is None
