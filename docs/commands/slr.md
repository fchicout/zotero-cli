# Command: `slr`

Systematic Literature Review (SLR) lifecycle management. This command provides a semantic namespace for managing screening, data loading, validation, and advanced research aids.

## Structure
The `slr` command is organized into a flat 2-level structure:
`zotero-cli slr <verb> [options]`

---

## Verbs

### `screen`
Starts the interactive Terminal User Interface (TUI) for screening items.

**Usage:**
```bash
zotero-cli slr screen --source "RAW_COLLECTION" --include "INC_COLLECTION" --exclude "EXC_COLLECTION"
```

### `decide`
Records a single screening decision for an item via CLI. Supports SDB v1.2 with phase isolation and evidence capture.

**Usage:**
```bash
zotero-cli slr decide --key "ITEMKEY" --vote "INCLUDE|EXCLUDE" --code "REASON_CODE" [--phase "full_text"] [--evidence "Found text about X..."]
```

### `load`
Retroactively imports screening decisions from a CSV file. Matches items by Key, DOI, or Title.

**Usage:**
```bash
zotero-cli slr load "decisions.csv" --reviewer "Persona" --phase "title_abstract" --force
```

### `validate`
Checks a collection for metadata completeness (DOI, Title, Abstract) and presence of required artifacts (PDFs, SDB notes).

**Usage:**
```bash
zotero-cli slr validate --collection "SCREENED_COLLECTION" [--verbose]
```

### `lookup`
Performs bulk metadata lookup for Zotero items using external APIs (Semantic Scholar, CrossRef).

**Usage:**
```bash
zotero-cli slr lookup --keys "KEY1,KEY2"
```

### `graph`
Generates a Citation Graph (DOT format) for the specified collections.

**Usage:**
```bash
zotero-cli slr graph --collections "Collection A, Collection B"
```

### `shift`
Detects drift/shifts between two library snapshots (JSON). Useful for auditing collection movements.

**Usage:**
```bash
zotero-cli slr shift --old snap1.json --new snap2.json
```

### `migrate`
Migrates existing SDB notes to the latest schema version (e.g., v1.1 to v1.2).

**Usage:**
```bash
zotero-cli slr migrate --collection "COLLECTION" [--dry-run]
```

### `sync-csv`
Synchronizes a local CSV state from Zotero screening notes. Useful for recovery or external analysis.

**Usage:**
```bash
zotero-cli slr sync-csv --collection "COLLECTION" --output "synced.csv"
```

### `prune`
Enforces mutual exclusivity between an 'Included' and 'Excluded' collection by removing intersections from the excluded set.

**Usage:**
```bash
zotero-cli slr prune --included "Accepted" --excluded "Rejected"
```

### `extract`
Manages data extraction schemas and operations. Supports initializing a new schema and validating an existing one.

**Usage:**
```bash
# Initialize a new schema template
zotero-cli slr extract --init [--output schema.yaml]

# Validate an existing schema
zotero-cli slr extract --validate [--schema schema.yaml]
```

---

### `snowball`
Citation snowballing workflow (Discovery and Review).

#### `snowball seed`
Adds seed papers to the snowballing discovery graph.
```bash
zotero-cli slr snowball seed KEY1 KEY2
```

#### `snowball discovery`
Runs the background discovery worker to find citations (Forward/Backward) for pending nodes.
```bash
zotero-cli slr snowball discovery [--limit 10]
```

#### `snowball review`
Starts the interactive TUI to review discovered citation candidates.
```bash
zotero-cli slr snowball review
```

#### `snowball import`
Ingests all `ACCEPTED` candidates from the graph into Zotero.
```bash
zotero-cli slr snowball import --collection "Discovery"
```

---

### `sdb`
Management and maintenance of the Screening Database (SDB) layer embedded in Zotero notes.

#### `sdb inspect`
Visualizes all SDB entries (decisions, criteria, personas) attached to an item in a detailed table.

**Usage:**
```bash
zotero-cli slr sdb inspect "ITEMKEY"
```

#### `sdb edit`
Surgically updates a specific SDB entry matched by persona and phase. Defaults to Dry-Run mode.

**Usage:**
```bash
zotero-cli slr sdb edit "ITEMKEY" --persona "Name" --phase "title_abstract" --set-decision "accepted"
```

**Parameters:**
*   `--persona`: (Required) The reviewer identity to match.
*   `--phase`: (Required) The screening phase to match.
*   `--set-decision`: Update decision to `accepted` or `rejected`.
*   `--set-criteria`: Update comma-separated reason codes.
*   `--set-reason`: Update detailed reason text.
*   `--set-reviewer`: Change the persona name on the record.
*   `--execute`: Actually commit changes to Zotero.

#### `sdb upgrade`
Batch upgrades legacy SDB notes within a collection to the latest schema (v1.2).

**Usage:**
```bash
zotero-cli slr sdb upgrade --collection "My Collection" [--execute]
```

---

### `reset`
Safely resets items by stripping all screening metadata (SDB notes, tags) and optionally moving them back to a raw collection.

**Usage:**
```bash
zotero-cli slr reset --collection "To Reset" [--target-collection "Raw"] [--execute]
```

---

### `rag`
Retrieval-Augmented Generation (RAG) Core. Manages semantic indexing and querying of library content.

#### `rag ingest`
Ingests all items in a collection into the local vector store for semantic search.
```bash
zotero-cli slr rag ingest --collection "Research"
```

#### `rag query`
Performs a semantic search against the vector store using natural language.
```bash
zotero-cli slr rag query --prompt "What are the key trends in LLM safety?" [--top-k 5]
```

#### `rag context`
Retrieves synthesized context snippets for a specific item key.
```bash
zotero-cli slr rag context --key "ITEMKEY"
```
