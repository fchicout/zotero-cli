# Command: `item`

Operations related to individual research papers or Zotero items.

## Verbs

### `inspect`
Display detailed metadata and child objects (notes, attachments) for an item.

**Usage:**
```bash
zotero-cli item inspect --key "ITEMKEY"
```

**Parameters:**
*   `--key`: (Required) The Zotero Item Key.
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
zotero-cli item list --collection "My Papers" --wide
zotero-cli item list --collection "My Papers" --fields key,title,creators,year,venue,doi --format csv > papers.csv
```

**Parameters:**
*   `--collection`: Name or Key of the collection.
*   `--root`: List top-level items not in any collection.
*   `--trash`: List items in the trash.
*   `--top-only`: Only show top-level items.
*   `--fields`: Comma-separated fields to show (e.g. `key,title,creators,year,venue,doi`). Also accepts raw Zotero field names such as `publicationTitle` or `volume`.
*   `-w`, `--wide`: Preset showing key, title, first author, year, venue and DOI. Can't be combined with `--fields`.
*   `-f`, `--format`: `table` (default), `json`, `csv`, or `markdown`. Non-table formats print only the data, so they can be piped (e.g. into `jq`) or redirected to a file.

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
zotero-cli item update --key "ITEMKEY" --doi "10.1101/new-doi" --title "Corrected Title"
```

**Parameters:**
*   `--key`: (Required) The Zotero Item Key.
*   `--doi`: Update the DOI field.
*   `--title`: Update the Title.
*   `--abstract`: Update the Abstract Note.
*   `--json`: Provide a raw JSON string for partial update.
*   `--version`: Optional item version for optimistic locking.

---

### `delete`
Permanently deletes an item and its attachments and notes. This is not Zotero's trash and **cannot be undone** (trash via the Web API is being verified in #402; `item trash` works offline). Preview with `--dry-run` first. To consolidate a genuine duplicate into another item instead of discarding it outright, use `item merge`.

**Usage:**
```bash
zotero-cli item delete --key "ITEMKEY" --dry-run   # show what would be deleted
zotero-cli item delete --key "ITEMKEY"
```

**Parameters:**
*   `--key`: (Required) The Zotero Item Key.
*   `--version`: Delete only if the item is still at this version (default: its current version). If it changed since, nothing is deleted and the command exits 1.
*   `--dry-run`: Show the item and its attachments/notes without deleting.

---

### `trash`
Moves an item into Zotero's trash, in `--offline` mode only, by writing directly to the local `zotero.sqlite` the same way Zotero Desktop's own client writes it (bumps `dateModified`/`clientDateModified`, marks the row dirty so Desktop's next sync pushes the change to the server, adds a `deletedItems` row - `version` is left untouched). Preview-only by default. Not supported in online/API mode, which has no documented reversible trash write - see `item delete` for the permanent alternative there.

**Usage:**
```bash
zotero-cli --offline item trash --key "ITEMKEY" --execute
```

**Parameters:**
*   `--key`: (Required) The Zotero Item Key.
*   `--execute`: Actually perform the write (default: preview only).
*   `--force`: Skip the interactive confirmation prompt.

---

### `restore`
Reverses `item trash`: removes an item from the trash, in `--offline` mode only, writing the same way Zotero Desktop's own client writes a restore. Does not undo any prior `item merge` relations left on the item - see `docs/help_specs/item_restore.md` for that known limitation.

**Usage:**
```bash
zotero-cli --offline item restore --key "ITEMKEY" --execute
```

**Parameters:**
*   `--key`: (Required) The Zotero Item Key.
*   `--execute`: Actually perform the write (default: preview only).
*   `--force`: Skip the interactive confirmation prompt.

---

### `hydrate`

Fills in missing metadata (abstract, date, venue, URL, creators, DOI) for items that have a DOI, an arXiv ID or a PMID, using the configured metadata providers. arXiv preprints also get the DOI and journal of their published version. It previews by default; `--execute` writes. Only empty fields are filled unless you pass `--overwrite`, and the title changes only when named in `--fields`.

**Usage:**

```bash
zotero-cli item hydrate (--key KEY | --collection NAME | --all) [--fields LIST] [--overwrite] [--by-title] [--execute | --dry-run] [-f table|json]
```

**Options:**

*   `--key` / `--collection` / `--all`: What to hydrate: one item, a collection's top-level items, or the whole library.
*   `--fields`: Comma-separated fields to fill: `doi`, `abstract`, `date`, `venue`, `url`, `creators`, `title` (default: all but `title`).
*   `--overwrite`: Also replace values that are already set.
*   `--by-title`: For items with no identifier, accept an exact title match (checked against year and first author).
*   `--execute`: Write the changes. Without it (or with `--dry-run`), only a preview is shown.
*   `-f`, `--format`: `table` (default) or `json`, a machine-readable report on stdout.

**Example:**

```bash
zotero-cli item hydrate --collection "Imported"            # preview
zotero-cli item hydrate --collection "Imported" --execute  # write
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
zotero-cli item purge --key "ITEMKEY" --files --notes --tags
```

**Parameters:**
*   `--key`: (Required) The Zotero Item Key.
*   `--files`: Purge all child attachments/files.
*   `--notes`: Purge all child notes.
*   `--tags`: Purge all tags associated with the item.
*   `--force`: Skip interactive confirmation.

---

### `transfer`
Transfer an item (metadata, notes, and attachments) between different Zotero libraries (e.g., from your Personal Library to a Group, or between Groups).

**Usage:**
```bash
zotero-cli item transfer --key "ITEMKEY" --target-group "123456" [--delete-source]
```

**Parameters:**
*   `--key`: (Required) The Zotero Item Key to transfer.
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
zotero-cli item pdf fetch --key "ITEMKEY"
```

#### `pdf strip`

Remove all PDF attachments from a single item.



**Usage:**

```bash

zotero-cli item pdf strip --key "ITEMKEY"

```



#### `pdf attach`

Attach a local file (PDF, PostScript, DVI, etc.) to a specific item.



**Usage:**

```bash

zotero-cli item pdf attach --key "ITEMKEY" --file "/path/to/local/paper.pdf"

```
