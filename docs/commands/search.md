# Command: `search`

Search for items in your Zotero library using keywords, titles, or exact DOIs.

## Usage
```bash
zotero-cli search [query] [--doi DOI] [--title TITLE] [--limit N] [--start N]
                   [--tag TAG]... [--type TYPE] [--collection NAME|KEY]
                   [--year YEAR|FROM-TO] [--added-since DATE] [--added-until DATE]
                   [--sort FIELD] [--direction asc|desc] [--fulltext] [--format table|json|csv|ndjson|keys]
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

### `--fulltext`
Search inside the PDFs' text instead of title, creator and year. Offline only: it reads the full-text index Zotero keeps in `fulltext.sqlite` next to `zotero.sqlite`.
```bash
zotero-cli --offline search --fulltext "retrieval augmented"
zotero-cli --offline search --fulltext "buffer overflow" --tag to-read --year 2020- --limit 10
```
Every word must appear in the text of one of the item's PDFs; results are ranked best first and show a relevance `Score` (`--format json|csv|ndjson` carry it as `score`). The score only orders results within one search; it is tiny for words found in most PDFs. Filters (`--tag`, `--type`, `--collection`, `--year`, ...) and `--limit`/`--start` apply as usual; `--doi`, `--title`, `--sort` and `--direction` do not. Words are searched literally: `OR`, `NEAR` and quotes are not query syntax. Annotations and notes are not in this index. Without `--offline`, or with a Zotero that doesn't keep its index in `fulltext.sqlite`, the command says what is missing.

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

For piping, `--format keys` prints one item key per line, written as each result arrives:
```bash
zotero-cli search --tag to-read --format keys > keys.txt
xargs -n1 zotero-cli item inspect --key < keys.txt
```
or in one pipeline: `search --tag to-read --format keys | xargs -n1 zotero-cli item inspect --key`.
Other list-style commands print their identifying column: `tag list --format keys` the tag names, `system jobs list --format keys` the job ids. A value with a line break in it is written with the break replaced by a space, so one line is always one value.

Saved searches can't be run: the Web API exposes their definitions but not their results.

---

## Output
The command displays a formatted table with the following columns:
*   **Key:** The unique Zotero item key.
*   **Title:** The item's title (truncated if too long).
*   **Authors:** List of authors (truncated if too many).
*   **Year:** Publication year.
*   **DOI:** The item's DOI.
