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

### `pdf`
PDF attachment operations for a specific item.

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
