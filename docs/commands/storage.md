# Command: `storage`

Manage storage and attachments, specifically handling the transition between cloud storage and local filesystem.

## Verbs

### `checkout`

Moves stored files (PDFs/Attachments) from Zotero cloud/webdav storage to a managed local storage directory, replacing the attachment with a link to the local file. This is useful for offloading Zotero storage or managing large libraries.

**Usage:**
```bash
zotero-cli storage checkout [--limit LIMIT] [--allow-group-library] [--execute | --dry-run]
```

**Options:**
* `--limit`: Maximum number of items to process in one run (Default: 50).
* `--allow-group-library`: Allow checkout from a group library. Refused by default, because the linked file's absolute local path (including your username) syncs to every group member and points nowhere on their machines.
* `--execute`: Check out the files. Mutually exclusive with `--dry-run`. Currently the default when neither flag is given (with a deprecation warning) - pass it explicitly; this changes to preview-by-default in 4.0 (Issue #378).
* `--dry-run`: Preview what would be checked out, without downloading, relinking, or creating the storage directory. Mutually exclusive with `--execute`.

**Example:**
```bash
zotero-cli storage checkout --limit 100 --execute
```
