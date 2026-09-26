# Command: `storage`

Manage storage and attachments, specifically handling the transition between cloud storage and local filesystem.

## Verbs

### `checkout`

Moves stored files (PDFs/Attachments) from Zotero cloud/webdav storage to a managed local storage directory, replacing the attachment with a link to the local file. This is useful for offloading Zotero storage or managing large libraries.

**Usage:**
```bash
zotero-cli storage checkout [--limit LIMIT] [--dry-run | --execute] [--allow-group-library]
```

**Options:**
* `--limit`: Maximum number of items to process in one run (Default: 50).
* `--dry-run`: List the attachments that would move, without changing anything.
* `--execute`: Move the files. In 3.x moving is still the default (with a deprecation warning); from 4.0 the command only previews unless `--execute` is given.
* `--allow-group-library`: Allow checkout from a group library. Refused by default, because the linked file's absolute local path (including your username) syncs to every group member and points nowhere on their machines.

**Example:**
```bash
zotero-cli storage checkout --limit 100 --dry-run    # preview
zotero-cli storage checkout --limit 100 --execute
```
