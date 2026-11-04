# Contributing

The whole catalog is built from the book files themselves — there is nothing to
edit by hand except the text fields described below.

## Add or update a book

1. Put the file in the language folder for its language:

   ```
   books/en/<slug>.epub   books/fr/<slug>.epub   books/de/<slug>.fb2   ...
   ```

   * the folder name is a BCP-47 code (`en`, `fr`, `pt-BR`, `zh-Hans`, ...);
   * keep the file name **ASCII**, lowercase, hyphen-separated where possible
     (it becomes a URL); a nicer display title goes in the JSON;
   * only add books that are public domain / freely redistributable.

2. Refresh the derived data with one command:

   ```bash
   pip install -r requirements.txt
   python3 scripts/update.py            # covers, then the JSON
   ```

   Add `--rename` if the download came with an unreadable name
   (`pg1342-images-3.epub`): it normalises files to `<title>-<author>.<ext>`
   (preview with `--dry-run`).

3. Commit the book, its cover and the regenerated `catalog/` together.

## Write a description

Add `source/overrides/<lang>/<slug>.json` next to the book:

```json
{
  "description": "…one or two sentences, in the language of the book…",
  "year": 1897,
  "license": "public-domain",
  "source": "https://www.gutenberg.org/ebooks/345"
}
```

That file wins over everything and survives deleting `catalog/` and rebuilding.
You can also just edit `description` inside `catalog/shards/<lang>.json` — those
fields are **preserved** on every run — but overrides keep the prose out of the
generated files. With neither, the description stays the `No description`
placeholder. See the README for the full field list.

## Before you push

```bash
python3 scripts/update.py --check   # must print "catalog check OK"
python3 tests/test_pipeline.py      # must print "OK"
```

CI runs exactly these two commands.
