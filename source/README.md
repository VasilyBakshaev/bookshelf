# source/

Optional, hand-written input that is *not* generated from the book files.

## `overrides/`

Per-book values that should win over both the book file and the committed
catalog. Useful when you want your text to survive a full regeneration
(deleting `catalog/` and rebuilding), or to keep prose out of the generated
JSON.

```
source/overrides/<lang>/<slug>.json
source/overrides/en/pg84-images-3.json
```

The file is a plain object with any of the human-editable book fields:

```json
{
  "description": "Frankenstein, or the Modern Prometheus.",
  "subjects": ["Science fiction", "Gothic fiction"],
  "year": 1818,
  "license": "public-domain",
  "source": "https://www.gutenberg.org/ebooks/84"
}
```

Precedence for each field:

```
override  >  value already in catalog/books/*.json  >  value read from the book
```

Derived fields (`id`, `language`, `format`, `cover`, `download`, `bytes`,
`sha256`) are always recomputed and cannot be overridden.
