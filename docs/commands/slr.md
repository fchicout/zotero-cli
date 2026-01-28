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
