"""Bounded image inspection and receipt helpers for visual evidence."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

from .errors import HarnessError


MAX_IMAGE_BYTES = 20 * 1024 * 1024


def inspect_image_bytes(data: bytes) -> tuple[str, int, int]:
    """Return MIME type and dimensions for a bounded PNG or JPEG payload."""
    if not isinstance(data, bytes) or not data or len(data) > MAX_IMAGE_BYTES:
        raise HarnessError("IMAGE_INVALID", "image is empty or exceeds the 20 MiB limit")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        if len(data) < 24 or data[12:16] != b"IHDR":
            raise HarnessError("IMAGE_INVALID", "PNG header is incomplete")
        width, height = struct.unpack(">II", data[16:24])
        media_type = "image/png"
    elif data.startswith(b"\xff\xd8"):
        media_type, width, height = _jpeg_dimensions(data)
    else:
        raise HarnessError("IMAGE_INVALID", "only PNG and JPEG images are supported")
    if width <= 0 or height <= 0 or width > 32768 or height > 32768:
        raise HarnessError("IMAGE_INVALID", "image dimensions are outside the supported range")
    return media_type, width, height


def _jpeg_dimensions(data: bytes) -> tuple[str, int, int]:
    offset = 2
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        marker = data[offset + 1]
        offset += 2
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(data):
            break
        length = int.from_bytes(data[offset:offset + 2], "big")
        if length < 2 or offset + length > len(data):
            break
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if length < 7:
                break
            height = int.from_bytes(data[offset + 3:offset + 5], "big")
            width = int.from_bytes(data[offset + 5:offset + 7], "big")
            return "image/jpeg", width, height
        offset += length
    raise HarnessError("IMAGE_INVALID", "JPEG dimensions could not be read")


def inspect_image_file(path: Path) -> dict:
    path = Path(path)
    if path.is_symlink():
        raise HarnessError("IMAGE_INVALID", "image file must not be a symlink")
    path = path.resolve()
    try:
        size = path.stat().st_size
    except FileNotFoundError as exc:
        raise HarnessError("IMAGE_INVALID", f"image file is missing: {path}") from exc
    if size <= 0 or size > MAX_IMAGE_BYTES:
        raise HarnessError("IMAGE_INVALID", "image file is unsafe, empty, or too large")
    data = path.read_bytes()
    media_type, width, height = inspect_image_bytes(data)
    return {
        "path": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "mediaType": media_type,
        "width": width,
        "height": height,
    }
