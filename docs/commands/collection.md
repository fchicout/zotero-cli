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
zotero-cli collection create "New Folder" --parent "Root Folder"
```

**Parameters:**
*   `name`: (Positional, Required) The name of the new collection.
*   `--parent`: Optional parent collection Name or Key.

---

### `rename`
Rename an existing collection.

**Usage:**
```bash
zotero-cli collection rename "Old Name" "New Name"
```

---

### `delete`
Delete a collection.

**Usage:**
```bash
zotero-cli collection delete "Target Name" --recursive
```

**Parameters:**
*   `key`: (Positional, Required) Collection Name or Key.
*   `--recursive`: Delete all items and sub-collections within this collection.

---

### `clean`
Remove all items from a collection without deleting the collection itself.

**Usage:**
```bash
zotero-cli collection clean --collection "Temp"
```

---

### `duplicates`
Identify duplicate items within specific collections based on DOI or Title.

**Usage:**
```bash
zotero-cli collection duplicates --collections "Folder A, Folder B"
```

---

### `pdf`
Bulk PDF attachment operations for an entire collection.

#### `pdf fetch`
Attempt to fetch and attach missing PDFs for all items in a collection.

**Usage:**
```bash
zotero-cli collection pdf fetch --collection "Inbox"
```

#### `pdf strip`
Remove all PDF attachments from all items in a collection.

**Usage:**
```bash
zotero-cli collection pdf strip --collection "Processed"
```