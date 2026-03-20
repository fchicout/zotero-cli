# Command: `search`

Search for items in your Zotero library using keywords, titles, or exact DOIs.

## Usage
```bash
zotero-cli search [query] [options]
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

---

## Output
The command displays a formatted table with the following columns:
*   **Key:** The unique Zotero item key.
*   **Title:** The item's title (truncated if too long).
*   **Authors:** List of authors (truncated if too many).
*   **Year:** Publication year.
*   **DOI:** The item's DOI.
