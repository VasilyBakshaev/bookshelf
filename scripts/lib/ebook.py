"""Read book metadata (and the embedded cover) straight from the file.

Supports EPUB (zip + OPF) and FB2 (XML). Other formats return an empty
metadata dict -- the catalog still lists them, just without auto-filled fields.
Only the Python standard library is used here; Pillow is only needed later,
in ``extract_covers.py``.
"""
from __future__ import annotations

import base64
import html
import posixpath
import re
import urllib.parse
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

XLINK_NS = "http://www.w3.org/1999/xlink"

_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/bmp": "bmp",
}


def _local(tag: str) -> str:
    """Strip the ``{namespace}`` prefix from an ElementTree tag."""
    return tag.rsplit("}", 1)[-1]


def _clean(value: str | None) -> str:
    """Strip HTML tags/entities and collapse whitespace."""
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _year(value: str | None) -> int | None:
    match = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", value or "")
    return int(match.group(1)) if match else None


def _empty() -> dict[str, Any]:
    return {
        "title": None,
        "authors": [],
        "language": None,
        "description": None,
        "subjects": [],
        "publisher": None,
        "year": None,
        "cover": None,  # {"data": bytes, "ext": "jpg", "media_type": "image/jpeg"}
    }


def read_ebook(path: Path) -> dict[str, Any]:
    """Return metadata for ``path`` based on its extension."""
    fmt = path.suffix.lower().lstrip(".")
    try:
        if fmt == "epub":
            return _read_epub(path)
        if fmt == "fb2":
            return _read_fb2(path)
    except (zipfile.BadZipFile, ET.ParseError, OSError, ValueError):
        # A broken file must never crash the catalog build.
        return _empty()
    return _empty()


# --- EPUB ------------------------------------------------------------------
def _read_epub(path: Path) -> dict[str, Any]:
    info = _empty()
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        opf_name = _find_opf(zf, names)
        if not opf_name:
            return info
        opf = ET.fromstring(zf.read(opf_name))
        base = posixpath.dirname(opf_name)

        meta_el = next((el for el in opf.iter() if _local(el.tag) == "metadata"), None)
        if meta_el is not None:
            for child in list(meta_el):
                name = _local(child.tag)
                text = _clean(child.text)
                if not text:
                    continue
                if name == "title" and not info["title"]:
                    info["title"] = text
                elif name == "creator":
                    info["authors"].append(text)
                elif name == "language" and not info["language"]:
                    info["language"] = text
                elif name == "description" and not info["description"]:
                    info["description"] = text
                elif name == "subject":
                    info["subjects"].append(text)
                elif name == "publisher" and not info["publisher"]:
                    info["publisher"] = text
                elif name == "date" and info["year"] is None:
                    info["year"] = _year(text)

        info["cover"] = _epub_cover(zf, opf, base)
    return info


def _find_opf(zf: zipfile.ZipFile, names: list[str]) -> str | None:
    lowered = {n.lower(): n for n in names}
    container_name = lowered.get("meta-inf/container.xml")
    if container_name:
        try:
            container = ET.fromstring(zf.read(container_name))
            for el in container.iter():
                if _local(el.tag) == "rootfile" and el.get("full-path"):
                    return el.get("full-path")
        except ET.ParseError:
            pass
    return next((n for n in names if n.lower().endswith(".opf")), None)


def _epub_cover(zf: zipfile.ZipFile, opf: ET.Element, base: str) -> dict[str, Any] | None:
    items = []
    for el in opf.iter():
        if _local(el.tag) == "item":
            items.append(
                {
                    "id": el.get("id") or "",
                    "href": el.get("href") or "",
                    "media_type": (el.get("media-type") or "").lower(),
                    "properties": el.get("properties") or "",
                }
            )
    by_id = {item["id"]: item for item in items}

    cover_id = None
    for el in opf.iter():
        if _local(el.tag) == "meta" and (el.get("name") or "").lower() == "cover":
            cover_id = el.get("content")

    candidate = None
    if cover_id and cover_id in by_id:
        candidate = by_id[cover_id]
    if candidate is None:
        candidate = next((i for i in items if "cover-image" in i["properties"]), None)
    if candidate is None:
        guide_href = next(
            (
                el.get("href")
                for el in opf.iter()
                if _local(el.tag) == "reference"
                and (el.get("type") or "").lower() == "cover"
            ),
            None,
        )
        if guide_href:
            target = _resolve(base, guide_href)
            candidate = next(
                (i for i in items if _resolve(base, i["href"]).lower() == target.lower()),
                None,
            )
    if candidate is None:
        candidate = next(
            (
                i
                for i in items
                if i["media_type"].startswith("image/") and "cover" in i["id"].lower()
            ),
            None,
        )
    if candidate is None or not candidate["href"]:
        return None
    if candidate["media_type"] and not candidate["media_type"].startswith("image/"):
        return None

    target = _resolve(base, candidate["href"])
    actual = next((n for n in zf.namelist() if n.lower() == target.lower()), None)
    if actual is None:
        return None

    ext = _IMAGE_TYPES.get(candidate["media_type"]) or _ext_of(candidate["href"])
    if ext is None:
        return None
    return {"data": zf.read(actual), "ext": ext, "media_type": candidate["media_type"]}


# --- FB2 -------------------------------------------------------------------
def _read_fb2(path: Path) -> dict[str, Any]:
    info = _empty()
    raw = Path(path).read_bytes()
    root = _parse_xml(raw)
    if root is None:
        return info

    title_info = _first(root, "title-info")
    if title_info is not None:
        info["title"] = _text(title_info, "book-title") or None
        info["language"] = _text(title_info, "lang") or None
        annotation = _first(title_info, "annotation")
        if annotation is not None:
            info["description"] = _clean("".join(annotation.itertext())) or None
        for author in _find_all(title_info, "author"):
            parts = [
                _text(author, part)
                for part in ("first-name", "middle-name", "last-name", "nickname")
            ]
            name = " ".join(p for p in parts if p)
            if name:
                info["authors"].append(name)
        for genre in _find_all(title_info, "genre"):
            text = _clean(genre.text)
            if text:
                info["subjects"].append(text)
        info["year"] = _year(_text(title_info, "date"))

    doc_info = _first(root, "document-info")
    if doc_info is not None:
        publisher = _text(doc_info, "publisher")
        if publisher:
            info["publisher"] = publisher
        if info["year"] is None:
            info["year"] = _year(_text(doc_info, "date"))

    info["cover"] = _fb2_cover(root, title_info) if title_info is not None else None
    return info


def _parse_xml(raw: bytes) -> ET.Element | None:
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        pass
    for encoding in ("utf-8", "windows-1251", "koi8-r"):
        try:
            return ET.fromstring(raw.decode(encoding))
        except (ET.ParseError, ValueError, UnicodeDecodeError):
            continue
    return None


def _fb2_cover(root: ET.Element, title_info: ET.Element) -> dict[str, Any] | None:
    coverpage = _first(title_info, "coverpage")
    if coverpage is None:
        return None
    image = _first(coverpage, "image")
    if image is None:
        return None
    href = image.get(f"{{{XLINK_NS}}}href") or image.get("href") or ""
    target_id = href.lstrip("#")
    if not target_id:
        return None
    for binary in _find_all(root, "binary"):
        if (binary.get("id") or "") == target_id:
            try:
                data = base64.b64decode("".join((binary.text or "").split()))
            except (ValueError, TypeError):
                return None
            media_type = (binary.get("content-type") or "").lower()
            ext = _IMAGE_TYPES.get(media_type) or _ext_of(target_id)
            if ext is None:
                return None
            return {"data": data, "ext": ext, "media_type": media_type}
    return None


# --- tiny XML helpers ------------------------------------------------------
def _resolve(base: str, href: str) -> str:
    href = urllib.parse.unquote(href.split("#", 1)[0].split("?", 1)[0])
    joined = posixpath.join(base, href) if base else href
    return posixpath.normpath(joined)


def _ext_of(name: str) -> str | None:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return ext if ext in {"jpg", "jpeg", "png", "gif", "webp", "bmp"} else None


def _first(el: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in el.iter() if _local(child.tag) == name), None)


def _find_all(el: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in el.iter() if _local(child.tag) == name]


def _text(el: ET.Element, name: str) -> str:
    child = _first(el, name)
    return _clean(child.text) if child is not None else ""

