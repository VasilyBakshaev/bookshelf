# bookshelf

A dead-simple way to host a free e-book catalog on GitHub and serve it to a
reader app: **books live in `books/<language>/`, a script turns them into
JSON, another script pulls the covers out.**

No backend, no database, no API keys. Commit the books + the generated JSON,
then let the app download `raw.githubusercontent.com` / jsDelivr.

```
bookshelf/
├── books/                       # the library — one folder per language
│   ├── en/                      #   (BCP-47 code: en, fr, pt-BR, zh-Hans, ...)
│   │   ├── dracula-bram-stoker.epub
│   │   └── …
│   └── fr/
│       └── …
├── covers/                      # GENERATED: 300px JPEG previews
│   ├── en/dracula-bram-stoker.jpg
│   └── fr/…
├── catalog/                     # GENERATED: the JSON the app consumes
│   ├── index.json               #   entry point: schema version + shards
│   ├── languages.json           #   language list for the picker
│   └── shards/
│       ├── en.json              #   one shard per language
│       └── fr.json
├── source/overrides/            # hand-written per-book text (wins over everything)
│   └── en/dracula-bram-stoker.json
├── schema/catalog.schema.json   # JSON Schema contract
├── scripts/
│   ├── update.py                # one command: [rename] -> covers -> build [-> check]
│   ├── build_catalog.py         # books/ + overrides -> catalog/*.json
│   ├── extract_covers.py        # embedded cover -> covers/<lang>/<slug>.jpg
│   └── lib/                     # shared code (EPUB/FB2 parsing, helpers)
├── tests/test_pipeline.py       # end-to-end tests
└── .github/workflows/validate.yml
```

Every sub-directory of `books/` is a language; the name is still checked against
a BCP-47 shape so a typo such as `books/englsh/` is easy to spot.

## Requirements

* Python 3.9+
* `pip install -r requirements.txt`  (Pillow for covers, jsonschema for `--check`)

## Quick start

```bash
pip install -r requirements.txt

python3 scripts/update.py            # covers + build — the everyday command
python3 scripts/update.py --check    # ...and verify everything is in sync
python3 scripts/update.py --rename   # ...also tidy unreadable file names
```

`update.py` just runs the two steps in the right order — **covers have to exist
before the build records a `cover` path** — and keeps the modules separate, so
`build_catalog.py` and `--check` still run on plain Python without Pillow.
After adding or removing books run it once and commit `books/`, `covers/` and
`catalog/` together.

## Adding a book

1. Drop the file into the matching language folder:
   `books/en/my-new-book.epub`
2. Refresh the derived data:
   ```bash
   python3 scripts/update.py            # add --rename if the name is unreadable
   ```
3. Commit `books/`, `covers/` and `catalog/`.

That's it. Title, authors, subjects and the cover are read straight from the
EPUB/FB2 file. For formats we cannot parse (`txt`, `pdf`, `docx`, ...) the book
is still listed; you just fill in the metadata yourself.

File names should stay ASCII (they end up in URLs). Display titles live in the
JSON, so `pg84-images-3.epub` with the title "Frankenstein" is perfectly fine.

### Unreadable file names

Downloaded books often arrive as `pg1342-images-3.epub`. Pass `--rename` and the
generator tidies them up to `<title>-<author>.<ext>` (moving the cover along):

```bash
python3 scripts/build_catalog.py --rename --dry-run   # preview only
python3 scripts/update.py --rename                    # apply, then rebuild
```

Only EPUB/FB2 are renamed (other formats carry no metadata to name them from),
the operation is idempotent, name clashes are skipped with a message, and your
hand-written `description`/`license` follow the file — entries are matched by
`sha256` as well as by `id`. Note that renaming changes a book's `id`, so run it
before shipping a catalog to an app that remembers reading positions.

## Editing descriptions (these are yours and are never overwritten)

`catalog/shards/*.json` is generated, **but the human-editable fields in it are
preserved on every run**. Every book also gets a `"No description"` placeholder
until you write something real, so a card never renders an empty blurb.

Two equivalent places to write it:

1. **In `source/overrides/`** (recommended, and what this repo does) — hand-
   written JSON, one file per book, that wins over everything and survives even
   deleting `catalog/` and rebuilding from scratch.
2. **Directly in the generated shard** — open `catalog/shards/en.json`, write the
   `description` (and `subjects`, `year`, `license`, `source`, ...), then re-run
   the build as often as you like: your text stays, only `bytes`/`sha256`/paths
   are refreshed.

Precedence, per field: **override file > values already in the shard > values
read from the book file**. A handful of fields are *derived* and always
recomputed, so do not bother editing them:

| Always recomputed | Preserved (yours) |
| --- | --- |
| `id`, `language`, `format`, `cover`, `download`, `bytes`, `sha256` | `title`, `authors`, `description`, `subjects`, `publisher`, `year`, `originalTitle`, `translator`, `license`, `source`, `addedAt` |

### Overrides

`source/overrides/<lang>/<slug>.json` mirrors `books/<lang>/<slug>.<ext>` — one
small file per book. This repository already ships one for every book:

```json
{
  "description": "A young solicitor's visit to a Transylvanian castle drags him, and everyone he loves, into the hunt for the undead Count Dracula.",
  "year": 1897,
  "license": "public-domain",
  "source": "https://www.gutenberg.org/ebooks/345"
}
```

Keeping the prose out of the generated files means the shards can be rebuilt
from scratch at any time without losing anything.


## The JSON the app reads

Start at `catalog/index.json`; it lists the shards. Load only the language the
user picked — never the whole catalog.

**`catalog/index.json`**
```json
{
  "schemaVersion": 1,
  "generatedAt": "2026-11-04T07:04:37Z",
  "languagesIndex": "catalog/languages.json",
  "shards": {
    "en": "catalog/shards/en.json",
    "fr": "catalog/shards/fr.json"
  }
}
```

**`catalog/languages.json`** — for the language picker
```json
{
  "schemaVersion": 1,
  "generatedAt": "2026-11-04T07:04:37Z",
  "languages": [
    { "code": "en", "name": "English", "nativeName": "English", "bookCount": 5 },
    { "code": "fr", "name": "French", "nativeName": "Français", "bookCount": 6 }
  ]
}
```

**`catalog/shards/en.json`** — one shard per language
```json
{
  "schemaVersion": 1,
  "language": "en",
  "generatedAt": "2026-11-04T07:36:05Z",
  "books": [
    {
      "id": "en/dracula-bram-stoker",
      "title": "Dracula",
      "authors": ["Bram Stoker"],
      "language": "en",
      "description": "A young solicitor's visit to a Transylvanian castle drags him…",
      "subjects": ["Horror tales", "Gothic fiction"],
      "year": 1897,
      "format": "epub",
      "cover": "covers/en/dracula-bram-stoker.jpg",
      "download": "books/en/dracula-bram-stoker.epub",
      "bytes": 602902,
      "sha256": "be5b12d762ceaacab5bfd0c1e510c8d36a0498cdde43790d6575d198fa9cd94d",
      "license": "public-domain",
      "source": "https://www.gutenberg.org/ebooks/345",
      "addedAt": "2026-11-04"
    }
  ]
}
```

| field | why it is there |
| --- | --- |
| `id` | Stable unique key (`<language>/<slug>`) — reuse it as the library progress key so a book downloaded twice is recognised. |
| `title`, `authors[]` | The listing. |
| `language` | Same BCP-47 code as the `books/<code>/` folder and `languages.json`. |
| `description` | Blurb on the card. Defaults to `No description`; write yours in `source/overrides/`. |
| `subjects[]` | Grouping / search. |
| `publisher`, `year` | Sorting and "old/новинки" filters. |
| `originalTitle`, `translator` | Optional. |
| `format` | `epub`/`fb2`/`txt`/... so the app knows before downloading and can hide formats it cannot open. |
| `cover` | Relative path to the preview (300px JPEG). |
| `download` | Relative path to the book file (`books/<lang>/<file>`). |
| `bytes` | Download progress and "you are about to download 25 MB" warnings. |
| `sha256` | Verify the file after download, before importing it. |
| `license` | Legal hygiene — set it (`public-domain`, `cc0`, ...). |
| `source` | Attribution / provenance (e.g. the Gutenberg URL). |
| `addedAt` | Set once, on first build. |

Paths are **relative** — the app keeps one `baseUrl` constant and joins it, so
moving from `raw.githubusercontent.com` to jsDelivr is a one-line change.

## Serving it

| | URL | notes |
| --- | --- | --- |
| raw | `https://raw.githubusercontent.com/<user>/<repo>/main/catalog/index.json` | simplest; short cache, no API limits, CORS `*` |
| jsDelivr | `https://cdn.jsdelivr.net/gh/<user>/<repo>@main/catalog/index.json` | long cache, CORS, faster; pin a tag for immutable URLs |

Do **not** read the catalog through `api.github.com` — that is rate-limited
(60 req/h) and would need a token in the app.

## Notes & limits

* GitHub warns above **50 MB per file** and blocks above 100 MB. The
  `*-images-3.epub` editions from Gutenberg include every illustration and can be
  large (e.g. `books/en/pride-and-prejudice-jane-austen.epub` is ~25 MB) — prefer
  the no-images EPUB when you do not need them. Big scans (PDF/DjVu) belong in
  GitHub Releases.
* `catalog/` is generated, but only the *derived* fields are rewritten, so both
  `source/overrides/` and hand-edits inside a shard are safe.
* `python3 scripts/update.py --check` (or `build_catalog.py --check`) is what CI
  runs: schema + `sha256`/`bytes` + "is the catalog up to date". Add `--strict`
  to also fail when an EPUB/FB2 has no extracted cover.
* `year` comes from the EPUB's `dc:date`, which for Gutenberg is the *ebook*
  release date — that is why every book here sets the real publication year in
  its override.

## License

The scripts and schema in this repository are MIT (see `LICENSE`). The books
are **not** covered by that license — each book keeps its own terms, recorded in
the `license` field. Only add books that are public domain or otherwise freely
redistributable.


