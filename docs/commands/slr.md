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
