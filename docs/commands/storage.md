# Command: `storage`

Manage storage and attachments, specifically handling the transition between cloud storage and local filesystem.

## Verbs

### `checkout`

Moves stored files (PDFs/Attachments) from Zotero cloud/webdav storage to a managed local storage directory, replacing the attachment with a link to the local file. This is useful for offloading Zotero storage or managing large libraries.

**Usage:**
```bash
zotero-cli storage checkout [--limit LIMIT]
```

**Options:**
* `--limit`: Maximum number of items to process in one run (Default: 50).

**Example:**
```bash
zotero-cli storage checkout --limit 100
```
