"""Generate tiny EPUB/FB2 fixtures for the pipeline tests.

These are throwaway files written into a temporary repo, never committed.
"""
from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path

from PIL import Image

CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def sample_cover(color: tuple[int, int, int] = (180, 40, 40), size=(600, 900)) -> bytes:
    """A solid-colour PNG used as an embedded cover."""
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def make_epub(path: Path, *, title: str, author: str, language: str,
              cover: bytes | None = None,
              description: str = "Auto description taken from the EPUB metadata.",
              subject: str = "Fiction", date: str = "1900") -> None:
    opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">urn:uuid:demo</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    <dc:language>{language}</dc:language>
    <dc:description>{description}</dc:description>
    <dc:subject>{subject}</dc:subject>
    <dc:date>{date}</dc:date>
    <meta name="cover" content="cover-img"/>
  </metadata>
  <manifest>
    <item id="cover-img" href="cover.png" media-type="image/png" properties="cover-image"/>
    <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="chapter1"/></spine>
</package>
"""
    chapter = ('<?xml version="1.0" encoding="UTF-8"?>'
               '<html xmlns="http://www.w3.org/1999/xhtml"><body><p>Hello</p></body></html>')
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", CONTAINER_XML)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/chapter1.xhtml", chapter)
        if cover is not None:
            zf.writestr("OEBPS/cover.png", cover)


def make_fb2(path: Path, *, title: str, first: str, last: str, language: str,
             cover: bytes | None = None, annotation: str = "FB2 annotation text.",
             date: str = "1920") -> None:
    coverpage = ""
    binary = ""
    if cover is not None:
        coverpage = '<coverpage><image xlink:href="#cover.png"/></coverpage>'
        binary = ('<binary id="cover.png" content-type="image/png">'
                  f'{base64.b64encode(cover).decode("ascii")}</binary>')
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0"
             xmlns:xlink="http://www.w3.org/1999/xlink">
  <description>
    <title-info>
      <genre>sf</genre>
      <author><first-name>{first}</first-name><last-name>{last}</last-name></author>
      <book-title>{title}</book-title>
      <annotation><p>{annotation}</p></annotation>
      <date>{date}</date>
      <lang>{language}</lang>
      {coverpage}
    </title-info>
    <document-info>
      <author><nickname>tester</nickname></author>
      <date value="2020-01-01">2020</date>
    </document-info>
  </description>
  <body><section><p>Text</p></section></body>
  {binary}
</FictionBook>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(xml, encoding="utf-8")
