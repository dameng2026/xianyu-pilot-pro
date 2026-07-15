import io
from pathlib import Path

import pytest
import requests
from PIL import Image

from app.services import xianyu_goods_sync as sync


def _png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (4, 4), (20, 40, 60)).save(output, format="PNG")
    return output.getvalue()


def _publisher(*, tenant_id=7, verifier=None, remote_loader=None):
    return sync.XianyuItemPublisher(
        "_m_h5_tk=token_12345; cookie2=value",
        tenant_id,
        asset_verifier=verifier or (lambda _tenant, _url, _key: len(_png_bytes())),
        remote_image_loader=remote_loader or (lambda _url: _png_bytes()),
    )


def test_local_publish_image_requires_exact_tenant_path_and_active_asset(monkeypatch, tmp_path):
    fake_module = tmp_path / "app" / "services" / "xianyu_goods_sync.py"
    fake_module.parent.mkdir(parents=True)
    monkeypatch.setattr(sync, "__file__", str(fake_module))
    image_path = tmp_path / "uploads" / "images" / "tenant-7" / "cover.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(_png_bytes())

    seen = []
    publisher = _publisher(
        verifier=lambda tenant, url, key: seen.append((tenant, url, key)) or image_path.stat().st_size
    )
    content = publisher._read_publish_image("/uploads/images/tenant-7/cover.png")

    assert content == _png_bytes()
    assert seen == [(7, "/uploads/images/tenant-7/cover.png", "tenant-7/cover.png")]


@pytest.mark.parametrize(
    "url",
    [
        "/uploads/images/tenant-8/cover.png",
        "/uploads/images/cover.png",
        "/uploads/images/tenant-7/%2e%2e/tenant-8/cover.png",
        "/uploads/images/tenant-7/..\\tenant-8\\cover.png",
    ],
)
def test_local_publish_image_rejects_other_tenant_legacy_and_traversal(url):
    with pytest.raises(ValueError):
        _publisher()._read_publish_image(url)


def test_local_publish_image_fails_closed_when_asset_is_not_active(monkeypatch, tmp_path):
    fake_module = tmp_path / "app" / "services" / "xianyu_goods_sync.py"
    fake_module.parent.mkdir(parents=True)
    monkeypatch.setattr(sync, "__file__", str(fake_module))
    image_path = tmp_path / "uploads" / "images" / "tenant-7" / "cover.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(_png_bytes())

    def inactive(*_args):
        raise ValueError("inactive")

    with pytest.raises(ValueError, match="inactive"):
        _publisher(verifier=inactive)._read_publish_image("/uploads/images/tenant-7/cover.png")


def test_remote_publish_image_rejects_private_dns_before_request(monkeypatch):
    monkeypatch.setattr(
        sync.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))],
    )
    monkeypatch.setattr(
        sync.requests,
        "get",
        lambda *_args, **_kwargs: pytest.fail("private destination must not be requested"),
    )

    with pytest.raises(ValueError, match="non-public"):
        sync._download_public_image_sync("https://localhost/internal.png")


class _Socket:
    def getpeername(self):
        return ("8.8.8.8", 443)


class _Connection:
    sock = _Socket()


class _Raw:
    _connection = _Connection()


class _Response:
    status_code = 200
    raw = _Raw()

    def __init__(self, *, headers, chunks=()):
        self.headers = headers
        self._chunks = chunks
        self.closed = False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        return iter(self._chunks)

    def close(self):
        self.closed = True


def test_remote_publish_image_rejects_oversize_content_length(monkeypatch):
    response = _Response(headers={"Content-Length": str(sync.MAX_IMAGE_BYTES + 1)})
    monkeypatch.setattr(
        sync.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("8.8.8.8", 443))],
    )
    monkeypatch.setattr(sync.requests, "get", lambda *_args, **_kwargs: response)

    with pytest.raises(ValueError, match="size limit"):
        sync._download_public_image_sync("https://images.example/large.png")
    assert response.closed


def test_publish_image_upload_failure_never_returns_original_url(monkeypatch):
    publisher = _publisher()
    monkeypatch.setattr(sync.time, "sleep", lambda *_args: None)
    monkeypatch.setattr(
        sync.requests,
        "post",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(requests.exceptions.Timeout()),
    )

    with pytest.raises(RuntimeError, match="超时"):
        publisher.upload_image_to_xianyu("https://images.example/cover.png")


def test_publisher_requires_a_positive_tenant_scope():
    with pytest.raises(ValueError, match="tenant_id"):
        _publisher(tenant_id=0)
