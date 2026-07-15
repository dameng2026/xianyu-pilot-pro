from __future__ import annotations

from pathlib import Path

import pytest

from app.api.v1.routes import misc
from app.main import app
from app.core.image_security import ValidatedImage
from app.services.upload_governance import GovernedUpload


class _DummyDb:
    pass


def test_automation_service_never_mounts_the_shared_upload_directory():
    assert all(getattr(route, "path", "") != "/uploads" for route in app.routes)


@pytest.mark.asyncio
async def test_legacy_global_media_endpoints_are_truthfully_unavailable(monkeypatch):
    monkeypatch.setattr(misc.os, "listdir", lambda *_args: (_ for _ in ()).throw(AssertionError("must not list")))
    monkeypatch.setattr(misc.os, "remove", lambda *_args: (_ for _ in ()).throw(AssertionError("must not delete")))

    listed = await misc.media_list(data={}, db=_DummyDb(), current_user={"tenant_id": 1})
    deleted = await misc.media_delete(
        data={"name": "another-tenant-file.png"},
        db=_DummyDb(),
        current_user={"tenant_id": 1},
    )

    assert listed.code == 410
    assert deleted.code == 410
    assert "未读取" in listed.msg
    assert "未删除" in deleted.msg


@pytest.mark.asyncio
async def test_url_image_import_stores_only_validated_bytes(monkeypatch, tmp_path: Path):
    image = ValidatedImage(
        content=b"validated-image",
        extension=".png",
        media_type="image/png",
        width=8,
        height=6,
    )

    async def _download(url: str):
        assert url == "https://images.example/cat.png"
        return image

    monkeypatch.setattr(misc, "download_public_image", _download)
    monkeypatch.setattr(misc, "_IMAGE_UPLOAD_BASE_DIR", str(tmp_path))

    async def _store(image, *, tenant_id, base_dir, **_kwargs):
        tenant_dir = Path(base_dir) / f"tenant-{tenant_id}"
        tenant_dir.mkdir(parents=True)
        saved_name = "url-img_test.png"
        (tenant_dir / saved_name).write_bytes(image.content)
        return GovernedUpload(
            asset_id=12,
            storage_key=f"tenant-{tenant_id}/{saved_name}",
            public_url=f"/uploads/images/tenant-{tenant_id}/{saved_name}",
            saved_name=saved_name,
            size=len(image.content),
            sha256="a" * 64,
        )

    monkeypatch.setattr(misc, "store_governed_image", _store)

    result = await misc.image_upload_from_url(
        data={"url": "https://images.example/cat.png"},
        db=_DummyDb(),
        current_user={"tenant_id": 3},
    )

    assert result.code == 200
    assert result.data["url"].endswith(".png")
    saved = tmp_path / "tenant-3" / result.data["name"]
    assert saved.read_bytes() == image.content


@pytest.mark.asyncio
async def test_url_image_import_does_not_echo_downloader_errors(monkeypatch):
    async def _fail(_url: str):
        raise RuntimeError("Authorization=secret-token provider response body")

    monkeypatch.setattr(misc, "download_public_image", _fail)

    result = await misc.image_upload_from_url(
        data={"url": "https://images.example/cat.png"},
        db=_DummyDb(),
        current_user={"tenant_id": 3},
    )

    assert result.code == 422
    assert "secret-token" not in result.msg
    assert "provider response" not in result.msg


@pytest.mark.asyncio
async def test_browser_user_cannot_self_publish_imported_media(monkeypatch):
    async def _unexpected(_url: str):
        raise AssertionError("unauthorized public import must fail before download")

    monkeypatch.setattr(misc, "download_public_image", _unexpected)
    result = await misc.image_upload_from_url(
        data={
            "url": "https://images.example/banner.png",
            "visibility": "public",
            "purpose": "carousel",
        },
        db=_DummyDb(),
        current_user={"tenant_id": 3, "user_id": 4, "auth_type": "user"},
    )

    assert result.code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("purpose", ["carousel", "open-source-content"])
async def test_internal_content_import_is_explicitly_public(
    monkeypatch, tmp_path: Path, purpose: str
):
    image = ValidatedImage(
        content=b"validated-image",
        extension=".png",
        media_type="image/png",
        width=8,
        height=6,
    )
    captured = {}

    async def _download(_url: str):
        return image

    async def _store(_image, **kwargs):
        captured.update(kwargs)
        return GovernedUpload(
            asset_id=13,
            storage_key="tenant-3/carousel.png",
            public_url="/uploads/images/tenant-3/carousel.png",
            saved_name="carousel.png",
            size=len(image.content),
            sha256="b" * 64,
        )

    monkeypatch.setattr(misc, "download_public_image", _download)
    monkeypatch.setattr(misc, "store_governed_image", _store)
    monkeypatch.setattr(misc, "_IMAGE_UPLOAD_BASE_DIR", str(tmp_path))

    result = await misc.image_upload_from_url(
        data={
            "url": "https://images.example/banner.png",
            "visibility": "public",
            "purpose": purpose,
        },
        db=_DummyDb(),
        current_user={"tenant_id": 3, "user_id": 0, "auth_type": "internal"},
    )

    assert result.code == 200
    assert captured["visibility"] == "public"
    assert captured["purpose"] == purpose
    assert captured["owner_type"] == "service"


@pytest.mark.asyncio
async def test_internal_content_import_rejects_unapproved_public_purpose(monkeypatch):
    async def _unexpected(_url: str):
        raise AssertionError("invalid public purpose must fail before download")

    monkeypatch.setattr(misc, "download_public_image", _unexpected)

    result = await misc.image_upload_from_url(
        data={
            "url": "https://images.example/avatar.png",
            "visibility": "public",
            "purpose": "avatar",
        },
        db=_DummyDb(),
        current_user={"tenant_id": 3, "user_id": 0, "auth_type": "internal"},
    )

    assert result.code == 403


@pytest.mark.asyncio
async def test_image_upload_checks_account_ownership_before_reading_file(monkeypatch):
    class _UnreadableUpload:
        content_type = "image/png"

        async def read(self, _size: int):
            raise AssertionError("file must not be read for a cross-tenant account")

    async def _not_owned(*_args, **_kwargs):
        return False

    monkeypatch.setattr(misc, "_account_belongs_to_tenant", _not_owned)

    result = await misc.image_upload(
        accountId=42,
        file=_UnreadableUpload(),
        db=_DummyDb(),
        current_user={"tenant_id": 8},
    )

    assert result.code == 404
    assert result.msg == "账号不存在"


@pytest.mark.asyncio
async def test_retired_caller_controlled_tenant_search_is_unavailable():
    result = await misc.internal_goofish_search(
        q="phone",
        tenant_id=999,
        current_user={"tenant_id": 1},
    )

    assert result.code == 410


def test_local_message_image_reader_rejects_traversal_and_non_image_content(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(misc, "_IMAGE_UPLOAD_BASE_DIR", str(tmp_path))
    (tmp_path / "not-an-image.png").write_bytes(b"<html>not an image</html>")

    with pytest.raises(ValueError):
        misc._read_uploaded_image_bytes("/uploads/images/../not-an-image.png")
    with pytest.raises(ValueError, match="无效"):
        misc._read_uploaded_image_bytes("/uploads/images/not-an-image.png")


def test_local_message_image_reader_requires_current_tenant_directory(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(misc, "_IMAGE_UPLOAD_BASE_DIR", str(tmp_path))

    with pytest.raises(ValueError):
        misc._read_uploaded_image_bytes(
            "/uploads/images/tenant-8/photo.png", tenant_id=7
        )
    with pytest.raises(ValueError):
        misc._read_uploaded_image_bytes(
            "/uploads/images/legacy-flat-photo.png", tenant_id=7
        )
