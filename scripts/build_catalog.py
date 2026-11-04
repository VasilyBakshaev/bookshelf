#!/usr/bin/env python3
"""Generate the JSON catalog (``catalog/*.json``) from the book folders.

Human-editable fields (``description``, ``subjects``, ``license``, ``source``,
``year``, ...) are **preserved** from the committed catalog, so re-running this
script never wipes your edits. Derived fields (``bytes``, ``sha256``,
``format``, ``download``/``cover`` paths) are recomputed every time.

Order of precedence for a field:  override > existing catalog > file metadata.

Usage:
    python3 scripts/build_catalog.py            # (re)generate catalog/*.json
    python3 scripts/build_catalog.py --check    # verify without writing (CI)
    python3 scripts/build_catalog.py --rename   # normalise book file names too
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import config as cfg  # noqa: E402
from lib import util  # noqa: E402
from lib.ebook import read_ebook  # noqa: E402
from lib.scan import iter_books  # noqa: E402

BOOKS_DIR_REL = cfg.REL_SHARDS_DIR


def load_existing(root: Path) -> dict[str, dict[str, Any]]:
    """Map ``id -> book`` for every entry currently committed in catalog/books."""
    result: dict[str, dict[str, Any]] = {}
    books_dir = root / BOOKS_DIR_REL
    if not books_dir.is_dir():
        return result
    for shard in sorted(books_dir.glob("*.json")):
        data = util.read_json(shard, {}) or {}
        for book in data.get("books", []):
            if isinstance(book, dict) and book.get("id"):
                result[book["id"]] = book
    return result


def auto_metadata(path: Path, fmt: str) -> dict[str, Any]:
    """Metadata read from the file itself (only for parseable formats)."""
    if fmt not in cfg.COVER_FORMATS:
        return {}
    info = read_ebook(path)
    auto: dict[str, Any] = {}
    if info.get("title"):
        auto["title"] = info["title"]
    if info.get("authors"):
        auto["authors"] = info["authors"]
    if info.get("description"):
        auto["description"] = info["description"]
    if info.get("subjects"):
        auto["subjects"] = info["subjects"]
    if info.get("publisher"):
        auto["publisher"] = info["publisher"]
    if info.get("year"):
        auto["year"] = info["year"]
    return auto


def computed_fields(root: Path, lang: str, slug: str, fmt: str, path: Path) -> dict[str, Any]:
    """Fields that always reflect the current state of the files on disk."""
    cover_path = root / cfg.REL_COVERS_DIR / lang / f"{slug}.jpg"
    return {
        "id": f"{lang}/{slug}",
        "language": lang,
        "format": fmt,
        "download": cfg.download_rel(lang, path.name),
        "cover": f"{cfg.REL_COVERS_DIR}/{lang}/{slug}.jpg" if cover_path.exists() else None,
        "bytes": util.file_size(path),
        "sha256": util.sha256_file(path),
    }


def desired_stem(metadata: dict[str, Any], fallback: str) -> str:
    """Readable file stem built from the title and the first author."""
    parts = []
    if metadata.get("title"):
        parts.append(util.slugify(metadata["title"]))
    authors = metadata.get("authors") or []
    if authors:
        parts.append(util.slugify(authors[0]))
    slug = "-".join(part for part in parts if part)
    return util.truncate_slug(slug or fallback, cfg.RENAME_MAX_SLUG)


def plan_renames(root: Path) -> list[tuple[str, str, str, Path]]:
    """List ``(language, old_slug, new_slug, path)`` for files worth renaming.

    Only parseable formats are touched: without metadata there is nothing to
    derive a readable name from. Collisions are skipped with a message.
    """
    candidates = []
    for lang, slug, fmt, path in iter_books(root):
        if fmt not in cfg.COVER_FORMATS:
            continue
        target = desired_stem(auto_metadata(path, fmt), slug)
        if target and target != slug:
            candidates.append((lang, slug, target, path))

    moving_away = {path for _, _, _, path in candidates}
    plan = []
    taken: set[str] = set()
    for lang, slug, target, path in candidates:
        new_id = f"{lang}/{target}"
        new_path = path.with_name(f"{target}{path.suffix}")
        if new_id in taken:
            print(f"  skip {lang}/{slug}: '{new_path.name}' is already taken")
            continue
        if new_path.exists() and new_path not in moving_away:
            print(f"  skip {lang}/{slug}: '{new_path.name}' already exists")
            continue
        taken.add(new_id)
        plan.append((lang, slug, target, path))
    return plan


def apply_renames(root: Path, dry_run: bool = False) -> int:
    """Rename book files to their readable ``<title>-<author>.<ext>`` name.

    The matching preview cover is moved along. Hand-written catalog fields are
    not lost: after a rename ``build`` re-associates entries by ``sha256``.
    """
    plan = plan_renames(root)
    for lang, old_slug, new_slug, old_path in plan:
        new_path = old_path.with_name(f"{new_slug}{old_path.suffix}")
        print(f"  {rel(root, old_path)} -> {rel(root, new_path)}")
        if dry_run:
            continue
        old_path.rename(new_path)
        old_cover = root / cfg.REL_COVERS_DIR / lang / f"{old_slug}.jpg"
        new_cover = root / cfg.REL_COVERS_DIR / lang / f"{new_slug}.jpg"
        if old_cover.exists() and not new_cover.exists():
            new_cover.parent.mkdir(parents=True, exist_ok=True)
            old_cover.rename(new_cover)
    return len(plan)


def merge_book(
    slug: str,
    auto: dict[str, Any],
    existing: dict[str, Any],
    override: dict[str, Any],
    computed: dict[str, Any],
) -> dict[str, Any]:
    """Combine the four sources into one book object in canonical field order."""
    merged: dict[str, Any] = {}
    for field in cfg.BOOK_FIELD_ORDER:
        if field in cfg.COMPUTED_FIELDS:
            merged[field] = computed.get(field)
        elif field in override:
            merged[field] = override[field]
        elif field in existing:
            merged[field] = existing[field]
        elif field in auto:
            merged[field] = auto[field]
        else:
            merged[field] = None

    if not merged.get("title"):
        merged["title"] = util.humanize_slug(slug)
    if not merged.get("authors"):
        merged["authors"] = [cfg.DEFAULT_AUTHOR]
    if not merged.get("license"):
        merged["license"] = cfg.DEFAULT_LICENSE
    if not merged.get("description"):
        merged["description"] = cfg.DEFAULT_DESCRIPTION
    if not merged.get("addedAt"):
        merged["addedAt"] = util.today()

    clean = {k: v for k, v in merged.items() if v not in (None, "", [], {})}
    return {k: clean[k] for k in cfg.BOOK_FIELD_ORDER if k in clean}


def build(root: Path) -> dict[str, Any]:
    """Build the whole catalog in memory (index, languages and per-language shards)."""
    existing = load_existing(root)
    # Index by content too: a renamed file keeps its sha256, so hand-written
    # fields follow the file to its new id.
    by_hash: dict[str, dict[str, Any]] = {}
    for previous in existing.values():
        if previous.get("sha256"):
            by_hash.setdefault(previous["sha256"], previous)
    per_lang: dict[str, list[dict[str, Any]]] = {}

    seen: dict[str, Path] = {}
    for lang, slug, fmt, path in iter_books(root):
        book_id = f"{lang}/{slug}"
        if book_id in seen:
            raise ValueError(f"duplicate book id '{book_id}' ({seen[book_id]} and {path})")
        seen[book_id] = path

        computed = computed_fields(root, lang, slug, fmt, path)
        previous = existing.get(book_id) or by_hash.get(computed["sha256"], {})
        book = merge_book(
            slug,
            auto_metadata(path, fmt),
            previous,
            util.read_json(root / cfg.REL_OVERRIDES_DIR / lang / f"{slug}.json", {}) or {},
            computed,
        )
        per_lang.setdefault(lang, []).append(book)

    for books in per_lang.values():
        books.sort(key=lambda b: (b.get("title", "").casefold(), b.get("id", "")))

    shards = {
        lang: {
            "schemaVersion": cfg.SCHEMA_VERSION,
            "language": lang,
            "generatedAt": util.iso_now(),
            "books": books,
        }
        for lang, books in sorted(per_lang.items())
    }

    languages = [
        {
            "code": lang,
            "name": cfg.language_name(lang)[0],
            "nativeName": cfg.language_name(lang)[1],
            "bookCount": len(books),
        }
        for lang, books in sorted(per_lang.items())
    ]

    index = {
        "schemaVersion": cfg.SCHEMA_VERSION,
        "generatedAt": util.iso_now(),
        "languagesIndex": cfg.LANGUAGES_INDEX_REL,
        "shards": {lang: f"{BOOKS_DIR_REL}/{lang}.json" for lang in sorted(per_lang)},
    }

    return {
        "index": index,
        "languages": {
            "schemaVersion": cfg.SCHEMA_VERSION,
            "generatedAt": util.iso_now(),
            "languages": languages,
        },
        "shards": shards,
    }


def rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _would_rewrite(existing: Any, data: dict[str, Any]) -> bool:
    """True when the file on disk differs from what we would write.

    Compares values *and* key order, but ignores ``generatedAt``: a fresh
    timestamp alone must never trigger a rewrite.
    """
    if not isinstance(existing, dict):
        return True
    if util.strip_generated_at(existing) != util.strip_generated_at(data):
        return True
    candidate = dict(data)
    candidate["generatedAt"] = existing.get("generatedAt")
    return util.dump_json(existing) != util.dump_json(candidate)


def write_json_if_changed(path: Path, data: dict[str, Any]) -> bool:
    """Write ``data`` only when the on-disk file really differs."""
    existing = util.read_json(path) if path.exists() else None
    if not _would_rewrite(existing, data):
        return False
    payload = dict(data)
    if isinstance(existing, dict) and util.strip_generated_at(existing) == util.strip_generated_at(payload):
        payload["generatedAt"] = existing.get("generatedAt")  # pure reformat
    else:
        payload["generatedAt"] = util.iso_now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(util.dump_json(payload), encoding="utf-8")
    return True


def write_catalog(root: Path, built: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    catalog_dir = root / cfg.REL_CATALOG_DIR
    books_dir = root / BOOKS_DIR_REL

    if write_json_if_changed(catalog_dir / cfg.INDEX_NAME, built["index"]):
        changed.append(rel(root, catalog_dir / cfg.INDEX_NAME))
    if write_json_if_changed(catalog_dir / cfg.LANGUAGES_NAME, built["languages"]):
        changed.append(rel(root, catalog_dir / cfg.LANGUAGES_NAME))

    wanted: set[str] = set()
    for lang, shard in built["shards"].items():
        wanted.add(f"{lang}.json")
        if write_json_if_changed(books_dir / f"{lang}.json", shard):
            changed.append(rel(root, books_dir / f"{lang}.json"))

    # Drop shards for languages that no longer have any books.
    if books_dir.is_dir():
        for stale in sorted(books_dir.glob("*.json")):
            if stale.name not in wanted:
                stale.unlink()
                changed.append(f"{rel(root, stale)} (removed)")
    return changed


def _targets(root: Path, built: dict[str, Any]) -> dict[Path, dict[str, Any]]:
    targets = {
        root / cfg.REL_CATALOG_DIR / cfg.INDEX_NAME: built["index"],
        root / cfg.REL_CATALOG_DIR / cfg.LANGUAGES_NAME: built["languages"],
    }
    for lang, shard in built["shards"].items():
        targets[root / BOOKS_DIR_REL / f"{lang}.json"] = shard
    return targets


def compare_with_disk(root: Path, built: dict[str, Any]) -> list[str]:
    """Report files that are missing or differ from a fresh build."""
    problems = []
    for path, expected in _targets(root, built).items():
        actual = util.read_json(path)
        if actual is None:
            problems.append(f"missing file: {rel(root, path)}")
        elif _would_rewrite(actual, expected):
            problems.append(f"out of date: {rel(root, path)} -- run build_catalog.py")
    return problems


def verify_integrity(root: Path, built: dict[str, Any], require_covers: bool = False) -> list[str]:
    """Ensure every catalog entry matches a real file and vice versa."""
    problems = []
    seen: set[str] = set()
    for shard in built["shards"].values():
        for book in shard["books"]:
            seen.add(book["download"])
            download = root / book["download"]
            if not download.is_file():
                problems.append(f"{book['id']}: missing file {book['download']}")
                continue
            if util.file_size(download) != book["bytes"]:
                problems.append(f"{book['id']}: size mismatch for {book['download']}")
            if util.sha256_file(download) != book["sha256"]:
                problems.append(f"{book['id']}: sha256 mismatch for {book['download']}")
            cover = book.get("cover")
            if cover and not (root / cover).is_file():
                problems.append(f"{book['id']}: missing cover {cover}")
            elif not cover and require_covers and book["format"] in cfg.COVER_FORMATS:
                problems.append(f"{book['id']}: no preview cover -- run extract_covers.py")
    for lang, _slug, _fmt, path in iter_books(root):
        rel_download = cfg.download_rel(lang, path.name)
        if rel_download not in seen:
            problems.append(f"{rel_download}: present on disk but not in the catalog")
    return problems


def validate_schema(root: Path, built: dict[str, Any]) -> list[str]:
    """Validate payloads against ``schema/catalog.schema.json`` (optional dep)."""
    try:
        import jsonschema
    except ImportError:
        return []
    schema = util.read_json(root / "schema" / "catalog.schema.json")
    if not isinstance(schema, dict) or "definitions" not in schema:
        return ["schema/catalog.schema.json is missing"]

    def validator_for(definition: str):
        document = dict(schema)
        document["$ref"] = f"#/definitions/{definition}"
        return jsonschema.Draft7Validator(document)

    problems = []
    plan: list[tuple[str, Any]] = [
        ("index", built["index"]),
        ("languages", built["languages"]),
    ]
    plan += [("shard", shard) for shard in built["shards"].values()]

    for definition, payload in plan:
        errors = sorted(validator_for(definition).iter_errors(payload),
                        key=lambda e: list(e.path))
        for error in errors:
            location = "/".join(str(part) for part in error.path) or "<root>"
            problems.append(f"schema/{definition}: {location}: {error.message}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=cfg.REPO_ROOT,
                        help="repository root (default: auto-detected)")
    parser.add_argument("--check", action="store_true",
                        help="verify the catalog without writing (for CI)")
    parser.add_argument("--strict", action="store_true",
                        help="with --check: also fail when an EPUB/FB2 has no extracted cover")
    parser.add_argument("--rename", action="store_true",
                        help="rename book files to <title>-<author>.<ext> before building")
    parser.add_argument("--dry-run", action="store_true",
                        help="with --rename: only print the planned renames")
    args = parser.parse_args(argv)

    if args.check and args.rename:
        print("build_catalog: --check and --rename are mutually exclusive", file=sys.stderr)
        return 2
    if args.dry_run and not args.rename:
        print("build_catalog: --dry-run requires --rename", file=sys.stderr)
        return 2

    root = args.root.resolve()

    if args.rename:
        print("rename plan (dry run):" if args.dry_run else "renaming book files:")
        renamed = apply_renames(root, dry_run=args.dry_run)
        if args.dry_run:
            return 0
        print(f"  {renamed} file(s) renamed" if renamed else "  nothing to rename")

    try:
        built = build(root)
    except ValueError as exc:
        print(f"build_catalog: {exc}", file=sys.stderr)
        return 2
    total = sum(len(shard["books"]) for shard in built["shards"].values())
    summary = f"{total} book(s) in {len(built['shards'])} language(s)"

    if args.check:
        problems = (validate_schema(root, built)
                    + compare_with_disk(root, built)
                    + verify_integrity(root, built, require_covers=args.strict))
        if problems:
            print("catalog check FAILED:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 1
        print(f"catalog check OK: {summary}")
        return 0

    changed = write_catalog(root, built)
    if changed:
        print("updated:")
        for item in changed:
            print(f"  {item}")
    else:
        print("catalog already up to date")
    print(f"build_catalog: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


