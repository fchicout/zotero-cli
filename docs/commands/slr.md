# Command: `slr`

The Systematic Literature Review (SLR) command consolidation. This command unifies analysis, screening, and auditing workflows into a single semantic namespace.

## Verbs

### `screen`

Starts the interactive TUI screening process for a collection.

**Usage:**
```bash
zotero-cli slr screen --source "SOURCE_COL" --include "INC_COL" --exclude "EXC_COL"
```

### `decide`

Records a screening decision (Include/Exclude) for a specific item.

**Usage:**
```bash
zotero-cli slr decide --key "ITEMKEY" --vote "INCLUDE|EXCLUDE" --code "REASON_CODE"
```

### `audit`

Checks a collection for metadata completeness and presence of attachments. Supports subcommands `check` and `import-csv`.

**Usage:**
```bash
zotero-cli slr audit check --collection "COLLECTION_NAME"
zotero-cli slr audit import-csv "file.csv" --reviewer "PERSONA"
```

### `lookup`

Performs external metadata lookup (Semantic Scholar/CrossRef) for items.

**Usage:**
```bash
zotero-cli slr lookup --keys "KEY1,KEY2"
```

### `graph`

Generates a citation graph for a collection.

**Usage:**
```bash
zotero-cli slr graph --collections "COL1,COL2"
```

### `shift`

Detects shifts between two library snapshots.

**Usage:**
```bash
zotero-cli slr shift --old "snap1.json" --new "snap2.json"
```

### `migrate`

Migrates audit notes to newer schema versions (e.g. v1.0 to v1.1).

**Usage:**
```bash
zotero-cli slr migrate --collection "COLLECTION_NAME" [--dry-run]
```

### `prune`

Enforces mutual exclusivity between two collections by removing items from the excluded collection if they are present in the included one.

**Usage:**
```bash
zotero-cli slr prune --included "INC_COL" --excluded "EXC_COL"
```

### `sync-csv`

Recovers or syncs a local CSV state from Zotero screening notes.

**Usage:**
```bash
zotero-cli slr sync-csv --collection "COLLECTION_NAME" --output "file.csv"
```