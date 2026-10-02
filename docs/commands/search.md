# Command: `search`

Search for items in your Zotero library using keywords, titles, or exact DOIs.

## Usage
```bash
zotero-cli search [query] [--doi DOI] [--title TITLE] [--limit N] [--start N]
                   [--tag TAG]... [--type TYPE] [--collection NAME|KEY]
                   [--year YEAR|FROM-TO] [--added-since DATE] [--added-until DATE]
                   [--sort FIELD] [--direction asc|desc] [--format table|json|csv]
```

---

## Options

### Keyword Search
Matches against title, creator (author), or year.
```bash
zotero-cli search "deep learning"
```

### `--doi`
Search for a specific item by its exact Digital Object Identifier (DOI).
```bash
zotero-cli search --doi "10.1145/3313831.3376227"
```

### `--title`
Search for items containing a specific substring in their title.
```bash
zotero-cli search --title "Attention is all you need"
```

### `--limit`
Limit the number of results displayed (default: 50).
```bash
zotero-cli search "transformer" --limit 10
```

### Filters
Filters work with or without a keyword, with the Web API and with `--offline`, and combine freely.
```bash
zotero-cli search --tag to-read --tag ml                  # both tags
zotero-cli search --tag "to-read || later" --type book    # either tag, books only
zotero-cli search --tag=-archived "attention"             # keyword, excluding a tag (note the =)
zotero-cli search --collection "Included" --year 2018-2022
zotero-cli search --added-since 2026-01-01 --sort dateAdded --direction asc
zotero-cli search "transformer" --limit 20 --start 20     # the second page
```
To exclude a tag write `--tag=-name` with the `=`: without it the shell hands `-name` to the parser as if it were an option.

`--year` and `--added-since`/`--added-until` are applied as results arrive (the Web API has no date range), so an item without a publication year never matches `--year`. `--doi` names one item and can't be combined with filters.

Saved searches can't be run: the Web API exposes their definitions but not their results.

---

## Output
The command displays a formatted table with the following columns:
*   **Key:** The unique Zotero item key.
*   **Title:** The item's title (truncated if too long).
*   **Authors:** List of authors (truncated if too many).
*   **Year:** Publication year.
*   **DOI:** The item's DOI.
