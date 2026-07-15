"""
Standalone checks for image upload path resolution and compression behavior.

This script intentionally avoids importing project modules so it can validate
the filesystem assumptions used by the upload flow in isolation.
"""

from __future__ import annotations

import io
import logging
import os
import struct
import zlib
from pathlib import Path

from PIL import Image, ImageDraw


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOODS_SYNC_PATH = PROJECT_ROOT / "app" / "services" / "xianyu_goods_sync.py"
MISC_ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "v1" / "routes" / "misc.py"
UPLOADS_DIR = PROJECT_ROOT / "uploads"
IMAGES_DIR = UPLOADS_DIR / "images"


def _compress_image(img_data: bytes, max_size: int = 5 * 1024 * 1024) -> bytes:
    """Mirror the compression behavior used before image upload."""
    try:
        img = Image.open(io.BytesIO(img_data))

        if img.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        max_width, max_height = 1920, 1920
        width, height = img.size
        if width > max_width or height > max_height:
            scale = min(max_width / width, max_height / height)
            new_size = (int(width * scale), int(height * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            logger.info("scaled image from %sx%s to %sx%s", width, height, new_size[0], new_size[1])

        quality = 85
        for _ in range(3):
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=quality, optimize=True)
            compressed = out.getvalue()
            if len(compressed) <= max_size:
                logger.info("compressed image size=%s quality=%s", len(compressed), quality)
                return compressed
            quality = max(30, quality - 25)
            logger.info("image still too large size=%s reducing quality to %s", len(compressed), quality)

        out = io.BytesIO()
        img.save(out, format="JPEG", quality=quality, optimize=True)
        compressed = out.getvalue()
        logger.info("compressed image at minimum quality size=%s quality=%s", len(compressed), quality)
        return compressed
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("compression failed, returning original bytes: %s", exc)
        return img_data


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _create_minimal_png(width: int = 1, height: int = 1, color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        payload = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + payload + crc

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = chunk(b"IHDR", ihdr_data)

    raw = b""
    for _ in range(height):
        raw += b"\x00"
        for _ in range(width):
            raw += bytes(color)

    compressed = zlib.compress(raw)
    idat = chunk(b"IDAT", compressed)
    iend = chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


def test_upload_path_consistency() -> None:
    print("=" * 60)
    print("path consistency")
    print("=" * 60)

    _assert(GOODS_SYNC_PATH.is_file(), f"missing goods sync file: {GOODS_SYNC_PATH}")
    _assert(MISC_ROUTE_PATH.is_file(), f"missing misc route file: {MISC_ROUTE_PATH}")

    old_base = (GOODS_SYNC_PATH.parent / "../../../").resolve()
    new_base = (GOODS_SYNC_PATH.parent / "../../").resolve()
    storage_base = (MISC_ROUTE_PATH.parent / "../../../../uploads/images").resolve()

    print(f"goods sync dir: {GOODS_SYNC_PATH.parent}")
    print(f"legacy base:   {old_base / 'uploads' / 'images' / 'test.png'}")
    print(f"current base:  {new_base / 'uploads' / 'images' / 'test.png'}")
    print(f"storage base:  {storage_base / 'test.png'}")

    old_resolved = (old_base / "uploads" / "images" / "test.png").resolve()
    new_resolved = (new_base / "uploads" / "images" / "test.png").resolve()
    storage_resolved = (storage_base / "test.png").resolve()

    _assert(old_resolved != new_resolved, "legacy and current paths unexpectedly match")
    _assert(new_resolved == storage_resolved, f"path mismatch new={new_resolved} storage={storage_resolved}")
    print("PASS path consistency")


def test_local_file_reading() -> None:
    print("=" * 60)
    print("local file reading")
    print("=" * 60)

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    uploads_base = (GOODS_SYNC_PATH.parent / "../../").resolve()
    test_file = IMAGES_DIR / "test_verify_001.png"
    test_file.write_bytes(_create_minimal_png(100, 100, (255, 0, 0)))

    image_url = "/uploads/images/test_verify_001.png"
    local_path = (uploads_base / image_url.lstrip("/")).resolve()

    print(f"image url:   {image_url}")
    print(f"local path:  {local_path}")
    print(f"actual file: {test_file}")

    try:
        _assert(local_path.is_file(), f"expected local file at {local_path}")
        image_bytes = local_path.read_bytes()
        _assert(len(image_bytes) > 0, "expected non-empty image bytes")
        print(f"PASS local file reading size={len(image_bytes)}")
    finally:
        if test_file.exists():
            test_file.unlink()


def test_image_compression() -> None:
    print("=" * 60)
    print("image compression")
    print("=" * 60)

    rgba_img = Image.new("RGBA", (2000, 2000), (255, 0, 0, 128))
    draw = ImageDraw.Draw(rgba_img)
    draw.ellipse([100, 100, 1900, 1900], fill=(0, 255, 0, 200))
    rgba_buffer = io.BytesIO()
    rgba_img.save(rgba_buffer, format="PNG")

    compressed = _compress_image(rgba_buffer.getvalue())
    compressed_img = Image.open(io.BytesIO(compressed))
    _assert(compressed_img.size[0] <= 1920, f"width too large: {compressed_img.size[0]}")
    _assert(compressed_img.size[1] <= 1920, f"height too large: {compressed_img.size[1]}")
    _assert(compressed_img.mode == "RGB", f"expected RGB mode, got {compressed_img.mode}")
    _assert(len(compressed) <= 5 * 1024 * 1024, f"compressed file exceeds limit: {len(compressed)}")
    print("PASS rgba compression")

    rgb_img = Image.new("RGB", (800, 600), (0, 0, 255))
    rgb_buffer = io.BytesIO()
    rgb_img.save(rgb_buffer, format="JPEG", quality=95)
    compressed_small = _compress_image(rgb_buffer.getvalue())
    compressed_small_img = Image.open(io.BytesIO(compressed_small))
    _assert(compressed_small_img.size == (800, 600), "small image dimensions should remain unchanged")
    print("PASS rgb size preservation")

    palette_img = Image.new("P", (100, 100))
    palette_buffer = io.BytesIO()
    palette_img.save(palette_buffer, format="PNG")
    compressed_palette = _compress_image(palette_buffer.getvalue())
    compressed_palette_img = Image.open(io.BytesIO(compressed_palette))
    _assert(compressed_palette_img.mode == "RGB", f"palette image should convert to RGB, got {compressed_palette_img.mode}")
    print("PASS palette conversion")


def test_cdn_response_parsing() -> None:
    print("=" * 60)
    print("cdn response parsing")
    print("=" * 60)

    responses = [
        {"url": "https://img.alicdn.com/i4/xxx.jpg"},
        {"data": {"url": "https://img.alicdn.com/i4/xxx.jpg"}},
        {"object": {"url": "https://img.alicdn.com/i4/xxx.jpg"}},
        {"result": {"url": "https://img.alicdn.com/i4/xxx.jpg"}},
        [{"url": "https://img.alicdn.com/i4/xxx.jpg"}],
        {"data": {}},
        {"data": {"fileUrl": "https://img.alicdn.com/i4/xxx.jpg"}},
    ]

    expected = "https://img.alicdn.com/i4/xxx.jpg"
    matched = 0

    for index, response in enumerate(responses, start=1):
        url = ""
        if isinstance(response, dict):
            data = response.get("data")
            obj = response.get("object")
            result = response.get("result")
            url = (
                response.get("url", "")
                or (data.get("url", "") if isinstance(data, dict) else "")
                or (obj.get("url", "") if isinstance(obj, dict) else "")
                or (result.get("url", "") if isinstance(result, dict) else "")
                or (data.get("fileUrl", "") if isinstance(data, dict) else "")
            )
        elif isinstance(response, list) and response and isinstance(response[0], dict):
            url = response[0].get("url", "")

        if url == expected:
            matched += 1
            print(f"[{index}] parsed {url}")
        else:
            print(f"[{index}] no url in response {response}")

    _assert(matched == 6, f"expected to parse 6 URLs, got {matched}")
    print("PASS cdn response parsing")


if __name__ == "__main__":
    checks = [
        ("path consistency", test_upload_path_consistency),
        ("local file reading", test_local_file_reading),
        ("image compression", test_image_compression),
        ("cdn response parsing", test_cdn_response_parsing),
    ]

    results: list[tuple[str, bool]] = []
    for name, check in checks:
        print()
        try:
            check()
            results.append((name, True))
        except Exception as exc:
            print(f"FAIL {name}: {exc}")
            results.append((name, False))

    print("\n" + "=" * 60)
    print("summary")
    print("=" * 60)

    all_pass = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{status} - {name}")
        all_pass = all_pass and passed

    if not all_pass:
        raise SystemExit(1)
