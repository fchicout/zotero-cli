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

### `add`
Manually create a new item within a specific collection.

**Usage:**
```bash
zotero-cli item add --collection "My Review" --title "Manually Added Paper" --authors "Doe, John, Smith, Jane"
```

**Parameters:**
*   `--collection`: (Required) Name or Key of the destination collection.
*   `--title`: (Required) The title of the new item.
*   `--type`: The Zotero item type (Default: `journalArticle`).
*   `--authors`: Comma-separated list of authors.
*   `--date`: Publication date.
*   `--abstract`: Abstract note content.

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
Permanently deletes an item from the Zotero library. The Zotero Web API only exposes a hard, permanent `DELETE` - there is no soft-delete/trash-write path, so this **cannot be undone**. To consolidate a genuine duplicate into another item instead of discarding it outright, use `item merge`.

**Usage:**
```bash
zotero-cli item delete --key "ITEMKEY"
```

**Parameters:**
*   `--key`: (Required) The Zotero Item Key.
*   `--version`: Optional item version (auto-resolved if omitted).

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

### `export`
Exports an item to a specified format (BibTeX, RIS, or Markdown).

**Usage:**
```bash
zotero-cli item export --key "ITEMKEY" --format md [--output ./export/]
```

**Parameters:**
*   `--key`: (Required) The Zotero Item Key.
*   `--format`: Output format. Supported: `bibtex`, `ris`, `md`.
*   `--output`: Destination directory or file path.

---

### `purge`
Purge specific assets (files, notes, tags) from an item without deleting the item itself.

**Usage:**
```bash
zotero-cli item purge "ITEMKEY" --files --notes --tags
```

**Parameters:**
*   `key`: (Positional, Required) The Zotero Item Key.
*   `--files`: Purge all child attachments/files.
*   `--notes`: Purge all child notes.
*   `--tags`: Purge all tags associated with the item.
*   `--force`: Skip interactive confirmation.

---

### `transfer`
Transfer an item (metadata, notes, and attachments) between different Zotero libraries (e.g., from your Personal Library to a Group, or between Groups).

**Usage:**
```bash
zotero-cli item transfer "ITEMKEY" --target-group "123456" [--delete-source]
```

**Parameters:**
*   `key`: (Positional, Required) The Zotero Item Key to transfer.
*   `--target-group`: (Required) The ID of the destination Zotero Group.
*   `--delete-source`: If specified, delete the item from the source library after a successful transfer.

---

### `merge`
Merges one or more duplicate items into a chosen master: unions tags and collection membership, moves notes/attachments onto the master, then permanently deletes the (now emptied) duplicates. Use `report duplicates` first to find candidate keys, or `report duplicates --export-plan` for a bulk-editable plan file. This is **permanent** — the Zotero Web API only supports hard delete, there is no undo the way Zotero Desktop's internal merge has.

**Usage:**
```bash
zotero-cli item merge --master "MASTERKEY" --duplicates "DUPKEY1,DUPKEY2"
zotero-cli item merge --master "MASTERKEY" --duplicates "DUPKEY1" --execute
zotero-cli item merge --from-plan duplicates_plan.csv --execute
```

**Parameters:**
*   `--master`: Zotero Key of the item to keep. Required unless `--from-plan` is given.
*   `--duplicates`: Comma-separated Zotero Keys of the duplicate items to merge into `--master`. Required unless `--from-plan` is given.
*   `--from-plan`: Path to a merge plan file (`.csv` or `.json`, from `report duplicates --export-plan`) for bulk execution of many groups at once, instead of a single `--master`/`--duplicates` group.
*   `--execute`: Actually perform the merge. Without it, only a preview is shown and nothing is written.
*   `--force`: Skip the interactive confirmation prompt (still requires `--execute`).

If master and duplicates disagree on a scalar field (title, date, DOI, ISBN, URL, abstract), the single-group form prompts you to pick which value to keep for each — there is no silent "first wins" default. Master and duplicates must share the same item type, matching the rule Zotero Desktop enforces for its own merge.

With `--from-plan`, every group in the file must already have a filled-in decision (`role`/`reason` columns in CSV, or a `decision` object in JSON) — if even one group is still unresolved, **nothing in the whole plan is written**, not just that group. Bulk merges default any conflicting scalar field to the chosen master's own current value rather than prompting (there's no interactive path in a batch run) — the human already made the real decision by choosing which occurrence is master.

---

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
