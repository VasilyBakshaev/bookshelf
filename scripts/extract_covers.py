#!/usr/bin/env python3
"""Extract embedded covers from books into ``covers/<lang>/<slug>.jpg``.

Previews are resized to COVER_WIDTH px wide (JPEG) so a list screen can load
them cheaply. Formats without an embedded image are skipped.

Usage:
    python3 scripts/extract_covers.py [--force] [--root DIR] [--width N]
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import config as cfg  # noqa: E402
from lib.ebook import read_ebook  # noqa: E402
from lib.scan import iter_books  # noqa: E402

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover - reported at runtime
    Image = None
    ImageOps = None


def to_jpeg(data: bytes, width: int, quality: int) -> bytes:
    """Decode any image, flatten transparency, resize to ``width`` and encode."""
    image = Image.open(io.BytesIO(data))
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        image = background
    else:
        image = image.convert("RGB")
    if image.width > width:
        height = round(image.height * width / image.width)
        image = image.resize((width, height), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=cfg.REPO_ROOT,
                        help="repository root (default: auto-detected)")
    parser.add_argument("--force", action="store_true",
                        help="re-extract covers even if the output already exists")
    parser.add_argument("--width", type=int, default=cfg.COVER_WIDTH,
                        help=f"preview width in px (default: {cfg.COVER_WIDTH})")
    args = parser.parse_args(argv)

    if Image is None:
        print("Pillow is required: pip install -r requirements.txt", file=sys.stderr)
        return 2

    root: Path = args.root.resolve()
    written = kept = missing = 0
    for lang, slug, fmt, path in iter_books(root):
        if fmt not in cfg.COVER_FORMATS:
            continue
        out = root / cfg.REL_COVERS_DIR / lang / f"{slug}.jpg"
        if out.exists() and not args.force:
            kept += 1
            continue
        cover = read_ebook(path).get("cover")
        if not cover:
            print(f"  no embedded cover: {lang}/{slug} ({fmt})")
            missing += 1
            continue
        try:
            payload = to_jpeg(cover["data"], args.width, cfg.COVER_JPEG_QUALITY)
        except Exception as exc:  # noqa: BLE001 - report and keep going
            print(f"  cannot decode cover for {lang}/{slug}: {exc}")
            missing += 1
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(payload)
        written += 1
        print(f"  covers/{lang}/{slug}.jpg")

    print(f"extract_covers: {written} written, {kept} kept, {missing} without cover")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
