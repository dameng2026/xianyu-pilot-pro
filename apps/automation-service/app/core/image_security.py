"""Bounded validation and download helpers for publicly served images."""

from __future__ import annotations

import io
import os
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

# 自动转 WebP 开关：上传 JPEG/PNG 时自动转为 WebP 以减小体积（约减少 30-50%）。
# 通过环境变量 UPLOAD_AUTO_WEBP=false 可关闭（默认开启）。
# GIF 不转换以保留动图；WebP 不需要再转；转换后体积反而变大的也保留原格式。
_AUTO_WEBP_ENABLED = os.getenv("UPLOAD_AUTO_WEBP", "true").lower() in ("1", "true", "yes", "on")
# WebP 质量：85 在视觉无损与体积之间取得良好平衡（参考 Pillow 官方推荐）
_WEBP_QUALITY = int(os.getenv("UPLOAD_WEBP_QUALITY", "85") or 85)
# 仅对大于此体积的图片做转换，过小的图片转换收益有限且可能反而变大
_WEBP_MIN_SOURCE_BYTES = 50 * 1024  # 50KB


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
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, SyntaxError) as exc:
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


def maybe_convert_to_webp(image: ValidatedImage) -> ValidatedImage:
    """将 JPEG/PNG 静态图自动转为 WebP 以减小体积；其余格式原样返回。

    转换条件（全部满足才转）：
    1. 全局开关 UPLOAD_AUTO_WEBP=true（默认开启）
    2. 源格式为 JPEG 或 PNG（GIF 保留动图、WebP 已是目标格式）
    3. 源体积 > 50KB（过小图片转换收益有限）
    4. 转换后体积严格更小（否则保留原格式）

    返回新的 ValidatedImage（content/extension/media_type/digest 都更新）。
    任何转换异常都不阻断上传，回退返回原图。
    """
    if not _AUTO_WEBP_ENABLED:
        return image
    source_format = None
    for fmt, (_, _) in _FORMAT_METADATA.items():
        # 通过 media_type 反查 format
        if image.media_type == _FORMAT_METADATA[fmt][1]:
            source_format = fmt
            break
    if source_format not in ("JPEG", "PNG"):
        return image
    if len(image.content) <= _WEBP_MIN_SOURCE_BYTES:
        return image

    try:
        with Image.open(io.BytesIO(image.content)) as img:
            # PNG 可能含 alpha 通道，转 WebP 时保留透明度
            buffer = io.BytesIO()
            save_kwargs: dict = {"format": "WEBP", "quality": _WEBP_QUALITY, "method": 4}
            if img.mode in ("RGBA", "LA", "P"):
                # P 模式（调色板）需要先转 RGBA 才能正确处理透明度
                if img.mode == "P":
                    img = img.convert("RGBA")
                save_kwargs["lossless"] = False
            img.save(buffer, **save_kwargs)
            webp_bytes = buffer.getvalue()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
        return image

    # 转换后体积反而变大（小图或已高度压缩），保留原格式
    if len(webp_bytes) >= len(image.content):
        return image

    return ValidatedImage(
        content=webp_bytes,
        extension=".webp",
        media_type="image/webp",
        width=image.width,
        height=image.height,
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
    "maybe_convert_to_webp",
    "validate_image_bytes",
]
