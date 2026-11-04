"""Central configuration: paths, formats and field policy.

Everything the two scripts need to agree on lives here so that
``extract_covers.py`` and ``build_catalog.py`` never drift apart.
"""
from __future__ import annotations

import re
from pathlib import Path

# --- paths -----------------------------------------------------------------
# scripts/lib/config.py  ->  repo root is two levels up.
SCRIPT_DIR = Path(__file__).resolve().parent   # scripts/lib
SCRIPTS_DIR = SCRIPT_DIR.parent                # scripts
REPO_ROOT = SCRIPTS_DIR.parent                 # repo root

# Books live under books/, one folder per language:
#     books/en/<slug>.epub
#     books/fr/<slug>.epub
# Every sub-directory of books/ is a language; the name is still checked
# against a BCP-47 shape so a typo such as books/englsh/ is easy to spot.
REL_BOOKS_DIR = "books"
LANGUAGE_DIR_PATTERN = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{1,8})*$")

REL_COVERS_DIR = "covers"
REL_CATALOG_DIR = "catalog"
REL_SHARDS_DIR = f"{REL_CATALOG_DIR}/shards"
REL_OVERRIDES_DIR = "source/overrides"

INDEX_NAME = "index.json"
LANGUAGES_NAME = "languages.json"

SCHEMA_VERSION = 1

# --- formats ---------------------------------------------------------------
# Formats the catalog knows about. COVER_FORMATS can embed a cover image we are
# able to pull out; other formats are still catalogued, just without a preview.
SUPPORTED_FORMATS = {
    "epub", "fb2", "txt", "docx", "pdf",
    "mobi", "azw3", "djvu", "cbz", "cbr", "html", "md",
}
COVER_FORMATS = {"epub", "fb2"}

# Files that are clearly not books and must be ignored when scanning files/.
IGNORED_STEMS = {"readme", "license", "licence", "changelog"}

# Preview cover settings.
COVER_WIDTH = 300           # preview width in px, height keeps the aspect ratio
COVER_JPEG_QUALITY = 85

# Renaming (``build_catalog.py --rename``): unreadable download names such as
# ``pg1342-images-3.epub`` become ``<title>-<author>.<ext>``.
RENAME_MAX_SLUG = 90        # hard cap for the generated file stem

# --- field policy ----------------------------------------------------------
# COMPUTED fields are recomputed on every run; every other field a human might
# edit is *preserved* from the committed catalog (or from an override file).
COMPUTED_FIELDS = frozenset(
    {"id", "language", "format", "download", "cover", "bytes", "sha256"}
)

# Canonical key order inside a book object (keeps git diffs readable).
BOOK_FIELD_ORDER = (
    "id", "title", "authors", "language", "description", "subjects",
    "publisher", "year", "originalTitle", "translator",
    "format", "cover", "download", "bytes", "sha256",
    "license", "source", "addedAt",
)

DEFAULT_LICENSE = "unknown"
DEFAULT_DESCRIPTION = "No description"
DEFAULT_AUTHOR = "Unknown"

LANGUAGES_INDEX_REL = f"{REL_CATALOG_DIR}/{LANGUAGES_NAME}"

# --- language display names ------------------------------------------------
# BCP-47 code -> (English name, native name). Unknown codes fall back to the
# code itself. Keep codes aligned with the reader app's language list.
LANGUAGE_NAMES: dict[str, tuple[str, str]] = {
    "af": ("Afrikaans", "Afrikaans"),
    "ar": ("Arabic", "العربية"),
    "az": ("Azerbaijani", "Azərbaycan"),
    "be": ("Belarusian", "Беларуская"),
    "bg": ("Bulgarian", "Български"),
    "ca": ("Catalan", "Català"),
    "cs": ("Czech", "Čeština"),
    "cy": ("Welsh", "Cymraeg"),
    "da": ("Danish", "Dansk"),
    "de": ("German", "Deutsch"),
    "el": ("Greek", "Ελληνικά"),
    "en": ("English", "English"),
    "eo": ("Esperanto", "Esperanto"),
    "es": ("Spanish", "Español"),
    "et": ("Estonian", "Eesti"),
    "eu": ("Basque", "Euskara"),
    "fa": ("Persian", "فارسی"),
    "fi": ("Finnish", "Suomi"),
    "fr": ("French", "Français"),
    "ga": ("Irish", "Gaeilge"),
    "gl": ("Galician", "Galego"),
    "he": ("Hebrew", "עברית"),
    "hi": ("Hindi", "हिन्दी"),
    "hr": ("Croatian", "Hrvatski"),
    "hu": ("Hungarian", "Magyar"),
    "hy": ("Armenian", "Հայերեն"),
    "id": ("Indonesian", "Bahasa Indonesia"),
    "is": ("Icelandic", "Íslenska"),
    "it": ("Italian", "Italiano"),
    "ja": ("Japanese", "日本語"),
    "ka": ("Georgian", "ქართული"),
    "kk": ("Kazakh", "Қазақша"),
    "ko": ("Korean", "한국어"),
    "la": ("Latin", "Latina"),
    "lt": ("Lithuanian", "Lietuvių"),
    "lv": ("Latvian", "Latviešu"),
    "mk": ("Macedonian", "Македонски"),
    "nl": ("Dutch", "Nederlands"),
    "no": ("Norwegian", "Norsk"),
    "pl": ("Polish", "Polski"),
    "pt": ("Portuguese", "Português"),
    "ro": ("Romanian", "Română"),
    "ru": ("Russian", "Русский"),
    "sk": ("Slovak", "Slovenčina"),
    "sl": ("Slovenian", "Slovenščina"),
    "sq": ("Albanian", "Shqip"),
    "sr": ("Serbian", "Српски"),
    "sv": ("Swedish", "Svenska"),
    "sw": ("Swahili", "Kiswahili"),
    "ta": ("Tamil", "தமிழ்"),
    "th": ("Thai", "ไทย"),
    "tr": ("Turkish", "Türkçe"),
    "uk": ("Ukrainian", "Українська"),
    "vi": ("Vietnamese", "Tiếng Việt"),
    "zh": ("Chinese", "中文"),
}


def language_name(code: str) -> tuple[str, str]:
    """Return (english_name, native_name) for a BCP-47 code."""
    return LANGUAGE_NAMES.get(code, (code, code))


def is_language_dir(name: str) -> bool:
    """True if ``name`` looks like a language folder (en, fr, pt-BR, ...)."""
    return bool(LANGUAGE_DIR_PATTERN.match(name))


def download_rel(language: str, filename: str) -> str:
    """Relative path of a book file, as stored in the JSON catalog."""
    return f"{REL_BOOKS_DIR}/{language}/{filename}"
