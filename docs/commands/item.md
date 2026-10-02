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
zotero-cli item move --key "ITEMKEY" --target "Target Collection"
```

**Parameters:**
*   `--key`: (Required) The Zotero Item Key.
*   `--item-id`: Deprecated alias of `--key` (removed in 4.0, Issue #379).
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
*   `-f`, `--format`: `table` (default), `json`, `csv`, `ndjson` (one JSON object per line) or `markdown`. Non-table formats print only the data, so they can be piped (e.g. into `jq`) or redirected to a file.

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
Permanently deletes an item from the Zotero library, which **cannot be undone** - unless you pass `--trash`, which moves it to Zotero's trash instead (the same as `item trash`). To consolidate a genuine duplicate into another item instead of discarding it outright, use `item merge`.

**Usage:**
```bash
zotero-cli item delete --key "ITEMKEY" --execute
```

**Parameters:**
*   `--key`: (Required) The Zotero Item Key.
*   `--version`: Optional item version (auto-resolved if omitted).
*   `--execute`: Delete the item. Mutually exclusive with `--dry-run`. Currently the default when neither flag is given (with a deprecation warning) - pass it explicitly; this changes to preview-by-default in 4.0 (Issue #378).
*   `--dry-run`: Preview the item and its children without deleting. Mutually exclusive with `--execute`.
*   `--trash`: Move the item to Zotero's trash (recoverable with `item restore`) instead of deleting it permanently. No deprecation warning, since it is recoverable. Trash becomes the default in 4.0, with `--permanent` for a hard delete (Issue #402, #462).

---

### `trash`
Moves an item into Zotero's trash, exactly as deleting it in Zotero Desktop would. Online it sets the item's `deleted` flag through the Web API (Desktop syncs it); with `--offline` it writes the same rows Desktop itself writes to the local `zotero.sqlite` (bumps `dateModified`/`clientDateModified`, marks the row dirty so Desktop's next sync pushes the change to the server, adds a `deletedItems` row - `version` is left untouched). Preview-only by default. The item keeps its collections and `item restore` brings it back.

**Usage:**
```bash
zotero-cli item trash --key "ITEMKEY" --execute
zotero-cli --offline item trash --key "ITEMKEY" --execute   # local zotero.sqlite instead
```

**Parameters:**
*   `--key`: (Required) The Zotero Item Key.
*   `--execute`: Actually perform the write (default: preview only).
*   `--force`: Skip the interactive confirmation prompt (only asked with `--offline`, which writes a live file).

---

### `restore`
Reverses `item trash`: removes an item from the trash, online through the Web API or with `--offline` by writing the same way Zotero Desktop's own client writes a restore. Does not undo any prior `item merge` relations left on the item - see `docs/help_specs/item_restore.md` for that known limitation.

**Usage:**
```bash
zotero-cli item restore --key "ITEMKEY" --execute
zotero-cli --offline item restore --key "ITEMKEY" --execute   # local zotero.sqlite instead
```

**Parameters:**
*   `--key`: (Required) The Zotero Item Key.
*   `--execute`: Actually perform the write (default: preview only).
*   `--force`: Skip the interactive confirmation prompt (only asked with `--offline`).

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
Exports an item to a specified format (BibTeX, RIS, Markdown, or a formatted bibliography).

**Usage:**
```bash
zotero-cli item export --key "ITEMKEY" --as md [--output ./export/]
zotero-cli item export --key "ITEMKEY" --as bibliography --style ieee [--render markdown] [--output refs.txt]
```

**Parameters:**
*   `--key`: (Required) The Zotero Item Key.
*   `--as`: Export type. Supported: `bibtex`, `ris`, `md`, `bibliography` (`--format` is the deprecated alias).
*   `--style`: With `--as bibliography`, the CSL citation style (default `apa`; e.g. `ieee`, `chicago-author-date`). An unknown style lists close matches. Styles bundled with `bxc` work offline.
*   `--render`: With `--as bibliography`: `plain` (default), `markdown` or `html`.
*   `--output`: Destination directory or file path. With `--as bibliography` it is optional: without it the bibliography is printed.

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
zotero-cli item transfer --key "ITEMKEY" --target-group "123456" [--delete-source [--trash]]
```

**Parameters:**
*   `--key`: (Required) The Zotero Item Key to transfer.
*   `--target-group`: (Required) The ID of the destination Zotero Group.
*   `--delete-source`: If specified, delete the item from the source library after a successful transfer.
*   `--trash`: With `--delete-source`, move the source item to Zotero's trash (recoverable with `item restore`) instead of deleting it permanently.

---

### `merge`
Merges one or more duplicate items into a chosen master: unions tags and collection membership, moves notes/attachments onto the master, then permanently deletes the (now emptied) duplicates - or, with `--trash`, moves them to Zotero's trash so the merge can be undone. Use `report duplicates` first to find candidate keys, or `report duplicates --export-plan` for a bulk-editable plan file. This is **permanent** — the Zotero Web API only supports hard delete, there is no undo the way Zotero Desktop's internal merge has.

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
*   `--trash`: Move the emptied duplicates to Zotero's trash (recoverable with `item restore`) instead of deleting them permanently (Issue #402).

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
