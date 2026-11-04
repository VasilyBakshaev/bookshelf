# Contributing

The whole catalog is built from the book files themselves — there is nothing to
edit by hand except the text fields described below.

## Add or update a book

1. Put the file in the language folder for its language:

   ```
   en/<slug>.epub      fr/<slug>.epub      de/<slug>.fb2      ...
   ```

   * the folder name is a BCP-47 code (`en`, `fr`, `pt-BR`, `zh-Hans`, ...);
   * keep the file name **ASCII**, lowercase, hyphen-separated where possible
     (it becomes a URL); a nicer display title goes in the JSON;
   * only add books that are public domain / freely redistributable.

2. Regenerate the derived data:

   ```bash
   pip install -r requirements.txt
   python3 scripts/extract_covers.py
   python3 scripts/build_catalog.py
   ```

3. Commit the book, its cover and the regenerated `catalog/` together.

## Write a description

Open `catalog/books/<lang>.json` and fill in `description` (and optionally
`subjects`, `year`, `license`, `source`). You can also set `license` — Gutenberg
books are normally `public-domain`.

These fields are **preserved** when `build_catalog.py` runs again, so it is safe
to keep editing them. See the README for the full field list.

If you prefer to keep your text outside the generated file, drop it in
`source/overrides/<lang>/<slug>.json` instead.

## Before you push

```bash
python3 scripts/build_catalog.py --check   # must print "catalog check OK"
python3 tests/test_pipeline.py             # must print "OK"
```

CI runs exactly these two commands.
