# Command: `item`

Operations related to individual research papers or Zotero items.

## Verbs

### `inspect`
Display detailed metadata and child objects (notes, attachments) for an item.

**Usage:**
```bash
zotero-cli item inspect "ITEMKEY"
```

**Parameters:**
*   `key`: (Positional, Required) The Zotero Item Key.
*   `--raw`: Show the raw JSON data from the Zotero API.
*   `--full-notes`: Display the full content of all child notes.

---

### `move`
Move an item from one collection to another.

**Usage:**
```bash
zotero-cli item move --item-id "ITEMKEY" --target "Target Collection"
```

**Parameters:**
*   `--item-id`: (Required) The Zotero Item Key.
*   `--target`: (Required) Name or Key of the destination collection.
*   `--source`: Optional source collection. If omitted, the tool attempts to infer the source.

---

### `list`
List items in a specific collection.

**Usage:**
```bash
zotero-cli item list --collection "My Papers" --top-only
```

**Parameters:**
*   `--collection`: Name or Key of the collection.
*   `--trash`: List items in the trash.
*   `--top-only`: Only show top-level items.

---

### `update`
Update specific metadata fields of an item.

**Usage:**
```bash
zotero-cli item update "ITEMKEY" --doi "10.1101/new-doi" --title "Corrected Title"
```

**Parameters:**
*   `key`: (Positional, Required) The Zotero Item Key.
*   `--doi`: Update the DOI field.
*   `--title`: Update the Title.
*   `--abstract`: Update the Abstract Note.
*   `--json`: Provide a raw JSON string for partial update.
*   `--version`: Optional item version for optimistic locking.

---

### `delete`
Move an item to the Zotero trash.

**Usage:**
```bash
zotero-cli item delete "ITEMKEY"
```

**Parameters:**
*   `key`: (Positional, Required) The Zotero Item Key.
*   `--version`: Optional item version.

---

### `hydrate`

Retroactively fetches latest metadata (DOI and Journal/Publication) for items originating from ArXiv. This is useful for "hydrating" pre-prints that were published in a peer-reviewed journal after they were added to Zotero.

**Usage:**

```bash
zotero-cli item hydrate "ITEMKEY" [--dry-run]
zotero-cli item hydrate --collection "COLLECTION_NAME"
zotero-cli item hydrate --all
```

**Options:**

*   `--dry-run`: Show what would be updated without applying changes.
*   `--collection`: Hydrate all ArXiv items within a specific collection.
*   `--all`: Scan the entire library for ArXiv items and attempt hydration.

**Example:**

```bash
zotero-cli item hydrate "ABCD1234"
```

### `pdf`

Operations related to PDF attachments.

#### `pdf fetch`
Attempt to fetch and attach a missing PDF for a single item.

**Usage:**
```bash
zotero-cli item pdf fetch "ITEMKEY"
```

#### `pdf strip`

Remove all PDF attachments from a single item.



**Usage:**

```bash

zotero-cli item pdf strip "ITEMKEY"

```



#### `pdf attach`

Attach a local file (PDF, PostScript, DVI, etc.) to a specific item.



**Usage:**

```bash

zotero-cli item pdf attach "ITEMKEY" "/path/to/local/paper.pdf"

```
