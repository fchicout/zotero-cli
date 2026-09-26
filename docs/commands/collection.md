# Command: `collection`

Manage the hierarchy and content of Zotero collections (folders).

## Verbs

### `list`
List all collections in the library.

**Usage:**
```bash
zotero-cli collection list
```

---

### `create`
Create a new collection.

**Usage:**
```bash
zotero-cli collection create --name "New Folder" --parent "Root Folder"
```

**Parameters:**
*   `--name`: (Required) The name of the new collection.
*   `--parent`: Optional parent collection name or key.

---

### `rename`
Rename an existing collection.

**Usage:**
```bash
zotero-cli collection rename --key "ABCD1234" --name "New Name"
```

**Parameters:**
*   `--key`: (Required) The collection's key (`collection list` shows it).
*   `--name`: (Required) The new name.
*   `--version`: Optional library version for optimistic locking.

---

### `delete`
Delete a collection. Without `--recursive`, only the collection goes and its items stay in your library. With `--recursive`, its sub-collections and the items filed only inside the tree are permanently deleted too; this previews first and needs `--execute` plus a confirmation (or `--yes`).

**Usage:**
```bash
zotero-cli collection delete --key "Target Name"                                  # collection only
zotero-cli collection delete --key "OLD_123" --recursive                          # preview
zotero-cli collection delete --key "OLD_123" --recursive --execute                # delete, after confirming
```

**Parameters:**
*   `--key`: (Required) Collection key, or a name that matches exactly one collection.
*   `--recursive`: Also delete sub-collections and the items filed only inside the tree.
*   `--execute`: With `--recursive`, actually delete (default: preview only).
*   `--yes`: Skip the confirmation (required when there's no terminal, e.g. in scripts).
*   `--include-shared`: Also delete items that are filed in collections outside the tree (kept by default).

Deletion through the Web API is permanent: it doesn't go through Zotero's trash.

---

### `clean`
Remove all items from a collection without deleting the collection or any item. The items stay in your library; those filed nowhere else appear under Unfiled Items. Previews by default.

**Usage:**
```bash
zotero-cli collection clean --collection "Temp"             # preview
zotero-cli collection clean --collection "Temp" --execute   # apply
```

---

### Duplicates and PDFs in a collection
These are not `collection` verbs:

*   Find duplicates within collections with `report duplicates`:
    ```bash
    zotero-cli report duplicates --collections "Folder A,Folder B"
    ```
*   Fetch missing PDFs for every item in a collection with `item pdf fetch`:
    ```bash
    zotero-cli item pdf fetch --collection "Inbox"
    ```
*   PDF attachments are removed one item at a time with `item pdf strip --key ITEMKEY` (see [item](item.md)).

---

### `backup`
Create a scoped backup of a specific collection tree.
Produces a `.zaf` archive containing only the items within the target collection.

**Usage:**
```bash
zotero-cli collection backup --name "My Review" --output "review_backup.zaf"
```

**Parameters:**
*   `--name`: (Required) Collection name or key.
*   `--output`: (Required) Output .zaf file path.

---

### `export`
Exports all items in a collection to a specified format (BibTeX, RIS, or Markdown).

**Usage:**
```bash
zotero-cli collection export --name "COLLECTION_NAME" --format bibtex [--output ./export/]
```

**Parameters:**
*   `--name`: (Required) The collection Name or Key.
*   `--format`: Output format. Supported: `bibtex`, `ris`, `md`.
*   `--output`: Destination directory or file path.

---

### `purge`
Permanently removes specific types of child assets (files, notes, tags) from every item in a collection, without deleting the items or the collection itself.

**Usage:**
```bash
zotero-cli collection purge --name "COLLECTION_NAME" --files --notes --tags --recursive
```

**Parameters:**
*   `--name`: (Required) The collection Name or Key.
*   `--files`: Purge attachments/files from all items in the collection.
*   `--notes`: Purge notes from all items in the collection.
*   `--tags`: Purge tags from all items in the collection.
*   `--recursive`: Apply the purge to sub-collections as well.
*   `--force`: Skip interactive confirmation.