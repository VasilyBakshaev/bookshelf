"""Scan ``files/<lang>/`` for catalogable books."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from . import config as cfg
from . import util


def iter_books(root: Path) -> Iterator[tuple[str, str, str, Path]]:
    """Yield ``(language, slug, format, path)`` for every book in the repo.

    Books live in top-level language folders (``en/``, ``fr/``, ...); see
    ``config.is_language_dir``. ``slug`` is the file stem. Dotfiles,
    unsupported extensions and obvious non-books (README/LICENSE) are skipped.
    """
    if not root.is_dir():
        return
    for lang_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        lang = lang_dir.name
        if not cfg.is_language_dir(lang):
            continue
        for path in sorted(lang_dir.iterdir()):
            if not path.is_file() or path.name.startswith("."):
                continue
            fmt = path.suffix.lower().lstrip(".")
            if fmt not in cfg.SUPPORTED_FORMATS:
                continue
            if path.stem.lower() in cfg.IGNORED_STEMS:
                continue
            yield lang, util.slugify(path.stem), fmt, path
