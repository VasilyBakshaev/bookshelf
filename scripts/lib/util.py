"""Small filesystem/JSON/text helpers shared by the scripts."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Minimal Cyrillic -> Latin transliteration so that a Russian title still
# yields an ASCII slug (file names in the repo must stay ASCII).
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "і": "i", "ї": "yi", "є": "ye", "ґ": "g",
}
_TRANSLIT_TABLE = str.maketrans(_TRANSLIT)


def iso_now() -> str:
    """UTC timestamp, e.g. ``2026-11-04T12:00:00Z``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    """UTC date, e.g. ``2026-11-04``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def slugify(value: str) -> str:
    """Turn any string into an ASCII, url-safe, hyphen-separated slug."""
    value = value.translate(_TRANSLIT_TABLE)
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "book"


def humanize_slug(slug: str) -> str:
    """``moby-dick`` -> ``Moby Dick`` (used as a fallback title)."""
    return " ".join(word.capitalize() for word in re.split(r"[-_.]+", slug) if word)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_size(path: Path) -> int:
    return path.stat().st_size


def read_json(path: Path, default: Any = None) -> Any:
    """Read JSON, returning ``default`` for a missing/corrupt file."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def dump_json(data: Any) -> str:
    """Pretty, stable JSON with a trailing newline (UTF-8, no escaping)."""
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def strip_generated_at(data: Any) -> Any:
    """Return a copy of ``data`` without ``generatedAt`` keys.

    Used to decide whether a file really changed: a fresh timestamp alone must
    not produce a diff.
    """
    if isinstance(data, dict):
        return {k: strip_generated_at(v) for k, v in data.items() if k != "generatedAt"}
    if isinstance(data, list):
        return [strip_generated_at(v) for v in data]
    return data
