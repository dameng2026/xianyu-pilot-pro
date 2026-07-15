from __future__ import annotations

import io

import httpx
import pytest
from PIL import Image

from app.core.image_security import MAX_IMAGE_BYTES, download_public_image, validate_image_bytes
from app.core.outbound_network import OutboundNetworkPolicy


async def _public_resolver(host: str, port: int) -> list[str]:
    return ["93.184.216.34"]


async def _private_resolver(host: str, port: int) -> list[str]:
    return ["127.0.0.1"]


def _png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 6), (20, 40, 60)).save(output, format="PNG")
    return output.getvalue()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://images.example/cat.png",
        "https://user:pass@images.example/cat.png",
        "https://images.example:8443/cat.png",
        "https://images.example/cat.png#fragment",
        "https://localhost/cat.png",
        "https://images.example\\@127.0.0.1/cat.png",
        "https://images.example/cat image.png",
    ],
)
async def test_public_image_import_rejects_unsafe_urls(url: str):
    policy = OutboundNetworkPolicy(resolver=_public_resolver)

    with pytest.raises(ValueError):
        await download_public_image(url, policy=policy)


@pytest.mark.asyncio
async def test_public_image_import_rejects_private_dns_resolution():
    policy = OutboundNetworkPolicy(resolver=_private_resolver)

    with pytest.raises(ValueError):
        await download_public_image("https://images.example/cat.png", policy=policy)


@pytest.mark.asyncio
async def test_public_image_import_accepts_bounded_matching_raster_content():
    png = _png_bytes()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.scheme == "https"
        assert request.url.host == "93.184.216.34"
        assert request.headers["Host"] == "images.example"
        assert request.extensions["sni_hostname"] == "images.example"
        return httpx.Response(
            200,
            headers={"Content-Type": "image/png", "Content-Length": str(len(png))},
            content=png,
        )

    image = await download_public_image(
        "https://images.example/cat.png",
        policy=OutboundNetworkPolicy(resolver=_public_resolver),
        transport=httpx.MockTransport(handler),
    )

    assert image.extension == ".png"
    assert image.media_type == "image/png"
    assert (image.width, image.height) == (8, 6)


@pytest.mark.asyncio
async def test_public_image_import_rejects_oversized_or_mismatched_responses():
    png = _png_bytes()

    async def oversized(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "image/png", "Content-Length": str(MAX_IMAGE_BYTES + 1)},
            content=png,
        )

    policy = OutboundNetworkPolicy(resolver=_public_resolver)
    with pytest.raises(ValueError, match="size limit"):
        await download_public_image(
            "https://images.example/cat.png",
            policy=policy,
            transport=httpx.MockTransport(oversized),
        )

    with pytest.raises(ValueError, match="does not match"):
        validate_image_bytes(png, declared_media_type="image/jpeg")


@pytest.mark.asyncio
async def test_public_image_import_does_not_follow_redirects():
    async def redirect(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://other.example/cat.png"})

    with pytest.raises(httpx.HTTPStatusError):
        await download_public_image(
            "https://images.example/cat.png",
            policy=OutboundNetworkPolicy(resolver=_public_resolver),
            transport=httpx.MockTransport(redirect),
        )


@pytest.mark.asyncio
async def test_public_image_import_rejects_dns_rebinding_to_private_connected_peer():
    class _PrivatePeer:
        def get_extra_info(self, name: str):
            assert name == "server_addr"
            return ("169.254.169.254", 443)

    async def rebound(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "image/png"},
            content=_png_bytes(),
            extensions={"network_stream": _PrivatePeer()},
        )

    with pytest.raises(ValueError, match="non-public peer"):
        await download_public_image(
            "https://images.example/cat.png",
            policy=OutboundNetworkPolicy(resolver=_public_resolver),
            transport=httpx.MockTransport(rebound),
        )
