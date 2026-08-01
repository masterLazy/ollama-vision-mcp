"""Load local image files into base64 data URLs for the vision API.

Includes lightweight safety checks (extension whitelist, size cap, magic
number sniff) and an optional auto-downscale for large images to keep local
Ollama inference fast.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20 MB
COMPRESS_THRESHOLD = 50 * 1024  # 50 KB
COMPRESS_MAX_DIM = 768

# Magic byte prefixes for supported formats.
IMAGE_MAGIC_PREFIXES = (
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"\xff\xd8\xff",  # JPEG
    b"GIF87a",  # GIF
    b"GIF89a",  # GIF
    b"RIFF",  # WEBP (RIFF....WEBP)
    b"BM",  # BMP
)

_MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def _mime_for(path: Path) -> str:
    return _MIME_BY_EXT.get(path.suffix.lower(), "image/png")


def _resolve(path_str: str, cwd: str) -> Path:
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = Path(cwd) / p
    return p.resolve()


def _validate(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Not a file: {path}")
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported image type '{path.suffix}' "
            f"(allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))})"
        )
    size = path.stat().st_size
    if size > MAX_IMAGE_BYTES:
        raise ValueError(f"Image too large: {size} bytes (max {MAX_IMAGE_BYTES})")


def _has_valid_magic(raw: bytes) -> bool:
    return any(raw.startswith(m) for m in IMAGE_MAGIC_PREFIXES)


def _maybe_compress(raw: bytes, path: Path, enabled: bool) -> tuple[bytes, str]:
    """Downscale large images via Pillow (pattern from looksee-mcp).

    Returns (bytes, mime). If compression is disabled, fails, or the image is
    small, the original bytes and MIME are returned unchanged.
    """
    if not enabled or len(raw) <= COMPRESS_THRESHOLD:
        return raw, _mime_for(path)
    try:
        from PIL import Image

        im = Image.open(io.BytesIO(raw))
        im.thumbnail((COMPRESS_MAX_DIM, COMPRESS_MAX_DIM), Image.LANCZOS)
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="JPEG", quality=65, optimize=True)
        return buf.getvalue(), "image/jpeg"
    except Exception:
        return raw, _mime_for(path)


def load_image(path_str: str, cwd: str, compress: bool = True) -> tuple[str, str]:
    """Read a local image and return (data_url, mime).

    `path_str` may be absolute or relative to `cwd`.
    """
    p = _resolve(path_str, cwd)
    _validate(p)
    raw = p.read_bytes()
    if not _has_valid_magic(raw):
        raise ValueError(f"File content does not look like a supported image: {p.name}")
    raw, mime = _maybe_compress(raw, p, compress)
    data_url = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
    return data_url, mime


def list_image_files(directory: str, cwd: str, create_if_missing: bool = False) -> list[str]:
    """Return absolute paths of image files in `directory`.

    If `create_if_missing` is True, the directory is created when absent
    (used for the default inbox so the user always has a place to drop images).
    """
    d = _resolve(directory, cwd)
    if not d.is_dir():
        if create_if_missing:
            d.mkdir(parents=True, exist_ok=True)
        else:
            raise NotADirectoryError(f"Not a directory: {d}")

    files = sorted(
        p for p in d.iterdir()
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS
    )
    return [str(p) for p in files]
