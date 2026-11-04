"""End-to-end tests for the catalog scripts.

Run with:  python3 tests/test_pipeline.py
       or:  python3 -m pytest tests
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import build_catalog  # noqa: E402
import extract_covers  # noqa: E402
from make_fixtures import make_epub, make_fb2, sample_cover  # noqa: E402


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class PipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="bookshelf-test-"))
        (self.tmp / "books/en").mkdir(parents=True)
        (self.tmp / "books/ru").mkdir(parents=True)
        shutil.copytree(ROOT / "schema", self.tmp / "schema")

        cover = sample_cover(size=(600, 900))
        make_epub(self.tmp / "books/en/moby-dick.epub",
                  title="Moby Dick", author="Herman Melville", language="en", cover=cover)
        make_epub(self.tmp / "books/en/no-cover.epub",
                  title="No Cover Book", author="A. Author", language="en", cover=None)
        make_fb2(self.tmp / "books/ru/skazka.fb2",
                 title="Сказка", first="Иван", last="Иванов", language="ru", cover=cover)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def build(self) -> int:
        return build_catalog.main(["--root", str(self.tmp)])

    def book(self, lang: str, book_id: str) -> dict:
        data = read_json(self.tmp / f"catalog/shards/{lang}.json")
        return next(b for b in data["books"] if b["id"] == book_id)

    # ------------------------------------------------------------------
    def test_01_build_creates_catalog(self) -> None:
        self.assertEqual(self.build(), 0)

        index = read_json(self.tmp / "catalog/index.json")
        self.assertEqual(set(index["shards"]), {"en", "ru"})
        self.assertEqual(index["schemaVersion"], 1)
        self.assertEqual(index["languagesIndex"], "catalog/languages.json")

        en = read_json(self.tmp / "catalog/shards/en.json")
        self.assertEqual({b["id"] for b in en["books"]}, {"en/moby-dick", "en/no-cover"})

        book = self.book("en", "en/moby-dick")
        self.assertEqual(book["title"], "Moby Dick")
        self.assertEqual(book["authors"], ["Herman Melville"])
        self.assertEqual(book["format"], "epub")
        self.assertEqual(book["download"], "books/en/moby-dick.epub")
        self.assertEqual(book["language"], "en")
        expected = hashlib.sha256(
            (self.tmp / "books/en/moby-dick.epub").read_bytes()).hexdigest()
        self.assertEqual(book["sha256"], expected)
        self.assertEqual(book["bytes"], (self.tmp / "books/en/moby-dick.epub").stat().st_size)

        languages = {x["code"]: x for x in read_json(self.tmp / "catalog/languages.json")["languages"]}
        self.assertEqual(languages["ru"]["nativeName"], "Русский")
        self.assertEqual(languages["ru"]["bookCount"], 1)
        self.assertEqual(languages["en"]["bookCount"], 2)

    def test_02_fb2_metadata_is_read(self) -> None:
        self.build()
        book = self.book("ru", "ru/skazka")
        self.assertEqual(book["title"], "Сказка")
        self.assertEqual(book["authors"], ["Иван Иванов"])
        self.assertEqual(book["year"], 1920)
        self.assertEqual(book["description"], "FB2 annotation text.")

    def test_03_build_is_idempotent(self) -> None:
        self.build()
        before = (self.tmp / "catalog/shards/en.json").read_text(encoding="utf-8")
        changed = build_catalog.write_catalog(self.tmp, build_catalog.build(self.tmp))
        self.assertEqual(changed, [])
        self.assertEqual((self.tmp / "catalog/shards/en.json").read_text(encoding="utf-8"), before)

    # ------------------------------------------------------------------
    def test_04_manual_fields_are_preserved(self) -> None:
        self.build()
        path = self.tmp / "catalog/shards/en.json"
        data = read_json(path)
        book = next(b for b in data["books"] if b["id"] == "en/moby-dick")
        book["description"] = "A hand-written description."
        book["subjects"] = ["Whales", "Adventure"]
        book["license"] = "public-domain"
        write_json(path, data)

        self.build()

        after = self.book("en", "en/moby-dick")
        self.assertEqual(after["description"], "A hand-written description.")
        self.assertEqual(after["subjects"], ["Whales", "Adventure"])
        self.assertEqual(after["license"], "public-domain")
        self.assertEqual(after["format"], "epub")  # derived fields still refreshed

    def test_05_overrides_take_precedence(self) -> None:
        overrides = self.tmp / "source/overrides/en"
        overrides.mkdir(parents=True)
        write_json(overrides / "moby-dick.json", {"description": "From override.", "license": "cc0"})
        self.build()
        book = self.book("en", "en/moby-dick")
        self.assertEqual(book["description"], "From override.")
        self.assertEqual(book["license"], "cc0")

        # a computed field can never be overridden
        write_json(overrides / "moby-dick.json", {"bytes": 999})
        self.build()
        self.assertNotEqual(self.book("en", "en/moby-dick")["bytes"], 999)

    def test_06_extract_covers_resizes(self) -> None:
        from PIL import Image

        self.assertEqual(extract_covers.main(["--root", str(self.tmp)]), 0)
        cover = self.tmp / "covers/en/moby-dick.jpg"
        self.assertTrue(cover.is_file())
        self.assertTrue(cover.read_bytes().startswith(b"\xff\xd8"))  # JPEG magic
        with Image.open(cover) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.width, 300)
            self.assertEqual(image.height, 450)  # 600x900 keeps its aspect ratio
        self.assertTrue((self.tmp / "covers/ru/skazka.jpg").is_file())
        self.assertFalse((self.tmp / "covers/en/no-cover.jpg").exists())

    def test_07_cover_path_is_recorded_and_kept(self) -> None:
        extract_covers.main(["--root", str(self.tmp)])
        self.build()
        self.assertEqual(self.book("en", "en/moby-dick")["cover"], "covers/en/moby-dick.jpg")

        path = self.tmp / "catalog/shards/en.json"
        data = read_json(path)
        next(b for b in data["books"] if b["id"] == "en/moby-dick")["description"] = "Mine."
        write_json(path, data)
        self.build()

        book = self.book("en", "en/moby-dick")
        self.assertEqual(book["description"], "Mine.")
        self.assertEqual(book["cover"], "covers/en/moby-dick.jpg")

    # ------------------------------------------------------------------
    def test_08_check_passes_then_detects_drift(self) -> None:
        extract_covers.main(["--root", str(self.tmp)])
        self.build()
        self.assertEqual(build_catalog.main(["--root", str(self.tmp), "--check"]), 0)

        target = self.tmp / "books/en/moby-dick.epub"
        target.write_bytes(target.read_bytes() + b"x")
        self.assertEqual(build_catalog.main(["--root", str(self.tmp), "--check"]), 1)

    def test_09_check_detects_missing_rebuild(self) -> None:
        self.build()
        (self.tmp / "books/en/extra.txt").write_text("plain text", encoding="utf-8")
        # files/ changed but the catalog was not regenerated
        self.assertEqual(build_catalog.main(["--root", str(self.tmp), "--check"]), 1)

    def test_10_strict_requires_covers(self) -> None:
        self.build()
        extract_covers.main(["--root", str(self.tmp)])
        self.build()
        self.assertEqual(build_catalog.main(["--root", str(self.tmp), "--check"]), 0)
        # no-cover.epub has no embedded image, so --strict keeps failing
        self.assertEqual(
            build_catalog.main(["--root", str(self.tmp), "--check", "--strict"]), 1)

    def test_11_schema_validation_is_clean(self) -> None:
        extract_covers.main(["--root", str(self.tmp)])
        self.build()
        built = build_catalog.build(self.tmp)
        self.assertEqual(build_catalog.validate_schema(self.tmp, built), [])

    def test_12_removing_last_book_drops_shard(self) -> None:
        self.build()
        self.assertTrue((self.tmp / "catalog/shards/ru.json").is_file())
        (self.tmp / "books/ru/skazka.fb2").unlink()
        self.build()
        self.assertFalse((self.tmp / "catalog/shards/ru.json").exists())
        self.assertEqual(set(read_json(self.tmp / "catalog/index.json")["shards"]), {"en"})

    def test_13_duplicate_book_id_is_reported(self) -> None:
        # "a-b.epub" and "A_B.epub" both slugify to the id "en/a-b"
        make_epub(self.tmp / "books/en/a-b.epub", title="First", author="X", language="en")
        make_epub(self.tmp / "books/en/A_B.epub", title="Second", author="Y", language="en")
        self.assertEqual(build_catalog.main(["--root", str(self.tmp)]), 2)

    # ------------------------------------------------------------------
    def test_14_rename_normalises_filenames(self) -> None:
        make_epub(self.tmp / "books/en/ugly-055.epub", title="My Great Book",
                  author="John Smith", language="en", cover=sample_cover())
        extract_covers.main(["--root", str(self.tmp)])
        self.build()

        path = self.tmp / "catalog/shards/en.json"
        data = read_json(path)
        next(b for b in data["books"] if b["id"] == "en/ugly-055")["description"] = "Kept."
        write_json(path, data)

        # --dry-run must not touch anything
        self.assertEqual(
            build_catalog.main(["--root", str(self.tmp), "--rename", "--dry-run"]), 0)
        self.assertTrue((self.tmp / "books/en/ugly-055.epub").is_file())

        self.assertEqual(build_catalog.main(["--root", str(self.tmp), "--rename"]), 0)

        self.assertFalse((self.tmp / "books/en/ugly-055.epub").exists())
        self.assertTrue((self.tmp / "books/en/my-great-book-john-smith.epub").is_file())
        self.assertTrue((self.tmp / "covers/en/my-great-book-john-smith.jpg").is_file())
        self.assertFalse((self.tmp / "covers/en/ugly-055.jpg").exists())

        book = self.book("en", "en/my-great-book-john-smith")
        self.assertEqual(book["description"], "Kept.")  # carried over by sha256
        self.assertEqual(book["download"], "books/en/my-great-book-john-smith.epub")
        self.assertEqual(book["cover"], "covers/en/my-great-book-john-smith.jpg")

    def test_15_rename_is_idempotent_and_guarded(self) -> None:
        self.assertEqual(build_catalog.main(["--root", str(self.tmp), "--rename"]), 0)
        self.assertEqual(build_catalog.plan_renames(self.tmp), [])

        # --check and --rename are mutually exclusive
        self.assertEqual(
            build_catalog.main(["--root", str(self.tmp), "--rename", "--check"]), 2)

    def test_16_description_defaults_to_a_placeholder(self) -> None:
        make_epub(self.tmp / "books/en/no-desc.epub", title="Silent",
                  author="A. Author", language="en", description="")
        self.build()
        book = self.book("en", "en/no-desc")
        self.assertEqual(book["description"], "No description")

        # an override replaces the placeholder and survives a rebuild
        overrides = self.tmp / "source/overrides/en"
        overrides.mkdir(parents=True)
        write_json(overrides / "no-desc.json", {"description": "A real blurb."})
        self.build()
        self.assertEqual(self.book("en", "en/no-desc")["description"], "A real blurb.")


if __name__ == "__main__":
    unittest.main(verbosity=2)


