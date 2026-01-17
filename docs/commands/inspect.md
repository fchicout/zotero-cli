# Command: `item inspect`

Inspect detailed metadata and children (notes/attachments) of a specific Zotero item.

**Usage:**
```bash
zotero-cli item inspect ITEM_KEY
```

**Options:**
*   `--raw`: Output the raw JSON data from Zotero API.
*   `--full-notes`: Display the complete content of child notes instead of a snippet.

**Example:**
```bash
zotero-cli item inspect ABC12345 --full-notes
```
