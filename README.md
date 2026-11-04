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
├── overrides/                   # hand-written text, one file per book
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

## Setup (once)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`.venv/` is git-ignored. Only `extract_covers.py` needs Pillow — `build_catalog.py`
and `--check` run on plain Python, and `jsonschema` is optional.

## Everyday use

```bash
python3 scripts/update.py            # extract covers, then build catalog/*.json
python3 scripts/update.py --check    # ...and verify everything is in sync
```

`update.py` runs the two steps in the right order — **covers have to exist before
the build records a `cover` path** — keeping the concerns in separate modules.
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

Title, authors, subjects and the cover are read straight from the EPUB/FB2 file.
For formats we cannot parse (`txt`, `pdf`, `docx`, ...) the book is still listed;
you just fill in the metadata yourself.

Keep file names ASCII (they end up in URLs) — the display title lives in the JSON.

### Unreadable file names

Downloaded books often arrive as `pg1342-images-3.epub`. Pass `--rename` and the
generator tidies them up to `<title>-<author>.<ext>` (moving the cover along):

```bash
python3 scripts/build_catalog.py --rename --dry-run   # preview only
python3 scripts/update.py --rename                    # apply, then rebuild
```

Only EPUB/FB2 are renamed, the operation is idempotent, clashes are skipped with
a message, and your hand-written text follows the file (entries are matched by
`sha256` as well as by `id`). Note that renaming changes a book's `id` — run it
before shipping a catalog to an app that remembers reading positions.

## Descriptions

`catalog/shards/*.json` is generated, **but the human-editable fields in it are
preserved on every run**. Every book gets `"No description"` until you write one,
and the tidy place to write it is `overrides/<lang>/<slug>.json` — one small file
per book (this repo ships one for each of them):

```json
{
  "description": "A young solicitor's visit to a Transylvanian castle drags him, and everyone he loves, into the hunt for the undead Count Dracula.",
  "year": 1897,
  "license": "public-domain",
  "source": "https://www.gutenberg.org/ebooks/345"
}
```

You can also edit `description` directly inside a shard — it is preserved too.
Precedence per field: **override > value already in the shard > value read from
the book file**. Always recomputed, so don't bother: `id`, `language`, `format`,
`cover`, `download`, `bytes`, `sha256`. Everything else is yours: `title`,
`authors`, `description`, `subjects`, `publisher`, `year`, `originalTitle`,
`translator`, `license`, `source`, `addedAt`.


## The JSON the app reads

Start at `catalog/index.json`; it lists the shards. Load only the language the
user picked — never the whole catalog.

**`catalog/index.json`** — the entry point: read it, then load one shard
```json
{ "schemaVersion": 1, "generatedAt": "…", "languagesIndex": "catalog/languages.json",
  "shards": { "en": "catalog/shards/en.json", "fr": "catalog/shards/fr.json" } }
```

**`catalog/languages.json`** — for the language picker
```json
{ "schemaVersion": 1, "generatedAt": "…", "languages": [
    { "code": "en", "name": "English", "nativeName": "English", "bookCount": 5 },
    { "code": "fr", "name": "French",  "nativeName": "Français", "bookCount": 6 } ] }
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
| `id` | Stable key (`<language>/<slug>`) — reuse it as the reading-progress key. |
| `title`, `authors[]` | The listing. |
| `language` | BCP-47 code, same as the `books/<code>/` folder. |
| `description` | Card blurb (`No description` until you write one). |
| `subjects[]`, `year` | Grouping, search, sorting. |
| `format` | So the app can hide formats it cannot open. |
| `cover`, `download` | Relative paths to the preview and the book file. |
| `bytes` | Download progress; "this is 25 MB" warnings. |
| `sha256` | Verify the file before importing it. |
| `license`, `source` | Legal hygiene and provenance. |
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

## Notes

* GitHub warns above **50 MB per file** and blocks above 100 MB. The
  `*-images-3.epub` editions include every illustration (ours is ~25 MB) — the
  no-images EPUB is smaller. Big scans (PDF/DjVu) belong in GitHub Releases.
* `year` comes from the EPUB's `dc:date`, which for Gutenberg is the *ebook*
  release date; the real publication year is set per book in `overrides/`.
* CI (`.github/workflows/validate.yml`) runs `build_catalog.py --check` and the
  tests on every push: schema + `sha256`/`bytes` + "is the catalog up to date".

## License

The scripts and schema in this repository are MIT (see `LICENSE`). The books
are **not** covered by that license — each book keeps its own terms, recorded in
the `license` field. Only add books that are public domain or otherwise freely
redistributable.


