"""Bounded validation and download helpers for publicly served images."""

from __future__ import annotations

import io
from dataclasses import dataclass

import httpx
from PIL import Image, UnidentifiedImageError

from .outbound_network import (
    OutboundNetworkPolicy,
    public_https_outbound_policy,
    require_expected_httpx_peer,
)


MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
_FORMAT_METADATA = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "GIF": (".gif", "image/gif"),
    "WEBP": (".webp", "image/webp"),
}
_ALLOWED_MEDIA_TYPES = {metadata[1] for metadata in _FORMAT_METADATA.values()}


@dataclass(frozen=True)
class ValidatedImage:
    content: bytes
    extension: str
    media_type: str
    width: int
    height: int


def validate_image_bytes(
    content: bytes,
    *,
    declared_media_type: str | None = None,
    max_bytes: int = MAX_IMAGE_BYTES,
) -> ValidatedImage:
    """Verify that bytes are a bounded raster image safe for same-origin serving."""

    if not content:
        raise ValueError("image is empty")
    if len(content) > max_bytes:
        raise ValueError("image exceeds the size limit")

    declared = str(declared_media_type or "").split(";", 1)[0].strip().lower()
    if declared and declared not in _ALLOWED_MEDIA_TYPES:
        raise ValueError("image media type is not supported")

    try:
        with Image.open(io.BytesIO(content)) as image:
            image_format = str(image.format or "").upper()
            width, height = image.size
            if image_format not in _FORMAT_METADATA:
                raise ValueError("image format is not supported")
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise ValueError("image dimensions exceed the limit")
            image.verify()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
        raise ValueError("image content is invalid") from exc

    extension, detected_media_type = _FORMAT_METADATA[image_format]
    if declared and declared != detected_media_type:
        raise ValueError("image media type does not match its content")
    return ValidatedImage(
        content=content,
        extension=extension,
        media_type=detected_media_type,
        width=width,
        height=height,
    )


async def download_public_image(
    raw_url: str,
    *,
    policy: OutboundNetworkPolicy = public_https_outbound_policy,
    max_bytes: int = MAX_IMAGE_BYTES,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ValidatedImage:
    """Download one public HTTPS raster image with strict transport limits."""

    target = await policy.pin_public_https(raw_url)
    timeout = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
    limits = httpx.Limits(max_connections=4, max_keepalive_connections=2)
    async with httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        follow_redirects=False,
        trust_env=False,
        headers={
            "Accept": "image/jpeg,image/png,image/gif,image/webp",
            "Host": target.host_header,
        },
        transport=transport,
    ) as client:
        async with client.stream(
            "GET",
            target.request_url,
            extensions={"sni_hostname": target.sni_hostname},
        ) as response:
            if transport is None or response.extensions.get("network_stream") is not None:
                require_expected_httpx_peer(response, target.peer_ip)
            response.raise_for_status()
            declared_media_type = response.headers.get("Content-Type", "")
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    declared_length = int(content_length)
                except ValueError as exc:
                    raise ValueError("image content length is invalid") from exc
                if declared_length < 0:
                    raise ValueError("image content length is invalid")
                if declared_length > max_bytes:
                    raise ValueError("image exceeds the size limit")

            chunks: list[bytes] = []
            downloaded = 0
            async for chunk in response.aiter_bytes():
                downloaded += len(chunk)
                if downloaded > max_bytes:
                    raise ValueError("image exceeds the size limit")
                chunks.append(chunk)

    return validate_image_bytes(
        b"".join(chunks),
        declared_media_type=declared_media_type,
        max_bytes=max_bytes,
    )

__all__ = [
    "MAX_IMAGE_BYTES",
    "MAX_IMAGE_PIXELS",
    "ValidatedImage",
    "download_public_image",
    "validate_image_bytes",
]
