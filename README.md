# bookshelf

A dead-simple way to host a free e-book catalog on GitHub and serve it to a
reader app: **books live in per-language folders, a script turns them into
JSON, another script pulls the covers out.**

No backend, no database, no API keys. Commit the books + the generated JSON,
then let the app download `raw.githubusercontent.com` / jsDelivr.

```
bookshelf/
├── en/                          # one folder per language (BCP-47 code)
│   ├── pg84-images-3.epub       #   the book files live here (as-is)
│   └── Dr_Jekyll_and_Mr_Hyde.epub
├── fr/
│   └── pg4650-images-3.epub
├── covers/                      # GENERATED: 300px JPEG previews
│   ├── en/pg84-images-3.jpg
│   └── fr/pg4650-images-3.jpg
├── catalog/                     # GENERATED: the JSON the app consumes
│   ├── index.json               #   entry point: schema version + shards
│   ├── languages.json           #   language list for the picker
│   └── books/
│       ├── en.json              #   one shard per language
│       └── fr.json
├── source/overrides/            # OPTIONAL per-book overrides (see below)
├── schema/catalog.schema.json   # JSON Schema contract
├── scripts/
│   ├── build_catalog.py         # files/ + overrides -> catalog/*.json
│   ├── extract_covers.py        # embedded cover -> covers/<lang>/<slug>.jpg
│   └── lib/                     # shared code (EPUB/FB2 parsing, helpers)
├── tests/test_pipeline.py       # end-to-end tests
└── .github/workflows/validate.yml
```

A **language folder** is any top-level directory whose name looks like a
BCP-47 code (`en`, `fr`, `pt-BR`, `zh-Hans`, ...). Everything else
(`scripts/`, `catalog/`, `schema/`, ...) is ignored automatically.

## Requirements

* Python 3.9+
* `pip install -r requirements.txt`  (Pillow for covers, jsonschema for `--check`)

## Quick start

```bash
pip install -r requirements.txt

python3 scripts/extract_covers.py    # 1. pull the covers out of the books
python3 scripts/build_catalog.py     # 2. (re)generate catalog/*.json
python3 scripts/build_catalog.py --check   # 3. verify everything is in sync
```

Run step 1 and 2 again after adding or removing any book, then commit
`en/`, `fr/`, `covers/` and `catalog/` together.

## Adding a book

1. Drop the file into the matching language folder:
   `en/my-new-book.epub`
2. Run the two scripts:
   ```bash
   python3 scripts/extract_covers.py
   python3 scripts/build_catalog.py
   ```
3. Commit `en/`, `covers/` and `catalog/`.

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
python3 scripts/build_catalog.py --rename             # apply, then rebuild
```

Only EPUB/FB2 are renamed (other formats carry no metadata to name them from),
the operation is idempotent, name clashes are skipped with a message, and your
hand-written `description`/`license` follow the file — entries are matched by
`sha256` as well as by `id`. Note that renaming changes a book's `id`, so run it
before shipping a catalog to an app that remembers reading positions.

## Editing descriptions (these are yours and are never overwritten)

`catalog/books/*.json` is generated, **but the human-editable fields in it are
preserved on every run**. Gutenberg EPUBs (and most sources) ship without a
`description`, so the usual workflow is:

1. Run the scripts once.
2. Open `catalog/books/en.json` and write the `description` (and `subjects`,
   `year`, `license`, `source`, ...).
3. Run `python3 scripts/build_catalog.py` again as often as you like —
   your text stays, only `bytes`/`sha256`/paths get refreshed.

Example — add this to a book object in `catalog/books/en.json`:

```json
"description": "Капитан Ахав охотится на белого кита...",
"subjects": ["Adventure", "Sea stories"],
"license": "public-domain",
"source": "https://www.gutenberg.org/ebooks/2701",
"year": 1851
```

Precedence, per field: **override file > values already in the JSON > values
read from the book file**. A handful of fields are *derived* and always
recomputed, so do not bother editing them:

| Always recomputed | Preserved from the JSON |
| --- | --- |
| `id`, `language`, `format`, `cover`, `download`, `bytes`, `sha256` | `title`, `authors`, `description`, `subjects`, `publisher`, `year`, `originalTitle`, `translator`, `license`, `source`, `addedAt` |

### Overrides (optional)

If you would rather keep your text out of the generated file — or you want it
to survive deleting `catalog/` and rebuilding from scratch — put it in
`source/overrides/<lang>/<slug>.json`:

```
source/overrides/en/pg84-images-3.json
```
```json
{ "description": "Frankenstein, or the Modern Prometheus.", "license": "public-domain" }
```

Override values win over everything except the derived fields.

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
    "en": "catalog/books/en.json",
    "fr": "catalog/books/fr.json"
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

**`catalog/books/en.json`** — one shard per language
```json
{
  "schemaVersion": 1,
  "language": "en",
  "generatedAt": "2026-11-04T07:04:37Z",
  "books": [
    {
      "id": "en/pg84-images-3",
      "title": "Frankenstein; or, The modern Prometheus",
      "authors": ["Mary Wollstonecraft Shelley"],
      "language": "en",
      "subjects": ["Science fiction", "Horror tales", "Gothic fiction"],
      "year": 1993,
      "format": "epub",
      "cover": "covers/en/pg84-images-3.jpg",
      "download": "en/pg84-images-3.epub",
      "bytes": 440131,
      "sha256": "0bfcc8cacdc72e132272844ed465c6198f1049a8d2b9e3f16806d02beee452e3",
      "license": "unknown",
      "addedAt": "2026-11-04"
    }
  ]
}
```

| field | why it is there |
| --- | --- |
| `id` | Stable unique key (`<language>/<slug>`) — reuse it as the library progress key so a book downloaded twice is recognised. |
| `title`, `authors[]` | The listing. |
| `language` | Same BCP-47 code as the folder and `languages.json`. |
| `description` | Blurb on the card / detail screen. **Fill this in by hand.** |
| `subjects[]` | Grouping / search. |
| `publisher`, `year` | Sorting and "old/новинки" filters. |
| `originalTitle`, `translator` | Optional. |
| `format` | `epub`/`fb2`/`txt`/... so the app knows before downloading and can hide formats it cannot open. |
| `cover` | Relative path to the preview (300px JPEG). |
| `download` | Relative path to the book file. |
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
  `*-images-3.epub` files from Gutenberg include every illustration and can be
  large (e.g. `pg1342-images-3.epub` is ~25 MB) — prefer the no-images EPUB
  when you do not need them. Big scans (PDF/DjVu) belong in GitHub Releases.
* `catalog/` is generated — but only the *derived* fields are rewritten, so
  committing your hand-written `description` is safe and expected.
* `python3 scripts/build_catalog.py --check` is what CI runs: schema +
  `sha256`/`bytes` + "is the catalog up to date". Add `--strict` to also fail
  when an EPUB/FB2 has no extracted cover.

## License

The scripts and schema in this repository are MIT (see `LICENSE`). The books
are **not** covered by that license — each book keeps its own terms, recorded in
the `license` field. Only add books that are public domain or otherwise freely
redistributable.


