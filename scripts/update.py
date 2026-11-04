#!/usr/bin/env python3
"""Refresh the catalog in one go: covers first, then the JSON.

Day-to-day entry point:

    python3 scripts/update.py            # extract covers + build the catalog
    python3 scripts/update.py --rename   # also rename files to readable names
    python3 scripts/update.py --check    # ...and verify the result

Covers must be written *before* the catalog is built, because the build only
records a ``cover`` path when the JPEG already exists. Keeping the two steps in
separate modules also keeps ``build_catalog.py`` free of the Pillow dependency.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_catalog  # noqa: E402
import extract_covers  # noqa: E402
from lib import config as cfg  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=cfg.REPO_ROOT,
                        help="repository root (default: auto-detected)")
    parser.add_argument("--rename", action="store_true",
                        help="rename book files to <title>-<author>.<ext> first")
    parser.add_argument("--check", action="store_true",
                        help="run the catalog check after building")
    args = parser.parse_args(argv)

    root = args.root.resolve()

    if args.rename:
        print("1. renaming book files")
        renamed = build_catalog.apply_renames(root)
        print(f"   {renamed} file(s) renamed" if renamed else "   nothing to rename")

    step = "2" if args.rename else "1"
    print(f"{step}. extracting covers")
    if extract_covers.main(["--root", str(root)]) == 2:
        print("   covers skipped -- run `pip install -r requirements.txt`")

    step = "3" if args.rename else "2"
    print(f"{step}. building the catalog")
    code = build_catalog.main(["--root", str(root)])
    if code != 0:
        return code

    if args.check:
        step = "4" if args.rename else "3"
        print(f"{step}. checking the catalog")
        return build_catalog.main(["--root", str(root), "--check"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
