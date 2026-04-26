# Command: `system`

The `system` command handles administrative tasks, information, and global library maintenance.

## Verbs

### `info`
Display library statistics, item counts, and sync status.

**Usage:**
```bash
zotero-cli system info
```

---

### `groups`
List all accessible Zotero Groups and their IDs.

**Usage:**
```bash
zotero-cli system groups
```

---

### `switch`
Switch the active library context to a specific Zotero Group.
This updates the local configuration to point to the selected group's library.

**Usage:**
```bash
zotero-cli system switch "My Research Group"
# OR use ID
zotero-cli system switch 1234567
```

**Parameters:**
*   `query`: (Positional, Required) Group Name (partial match supported) or Group ID.

---

### `backup`
Creates a complete, self-contained backup archive (`.zaf`) of your entire Zotero library or a specific collection, including all metadata and PDF attachments. Every attachment is mathematically verified using SHA-256 checksums.

**Usage:**
```bash
zotero-cli system backup --output "full_backup_2026.zaf"
```

**Parameters:**
*   `--output`: (Required) Path to save the backup file.

---

### `verify`
Performs a deep integrity check on a `.zaf` archive. Validates all internal JSON structures and re-calculates checksums for every attachment to ensure 100% data fidelity.

**Usage:**
```bash
zotero-cli system verify --file "backup.zaf"
```

**Parameters:**
*   `--file`: (Required) Path to the .zaf archive.

---

### `restore`
Reconstructs an entire Zotero library or specific collections from a `.zaf` archive. Implements intelligent duplicate detection (via DOI/ArXiv/Title) to avoid cluttering your library during restoration.

**Usage:**
```bash
zotero-cli system restore --file "backup.zaf" [--dry-run]
```

**Parameters:**
*   `--file`: (Required) Path to the .zaf archive.
*   `--dry-run`: (Optional) Simulates the restore without making any changes.

---

### `normalize`
Convert external CSV files (IEEE Xplore, Springer) into the Zotero-CLI Canonical format.
This allows for consistent pre-processing and manual auditing before importing to Zotero.

**Usage:**
```bash
zotero-cli system normalize "ieee_export.csv" --output "papers_ready.csv"
```

**Features:**
*   Automatic detection of IEEE and Springer formats.
*   Maps disparate headers to a single canonical schema.
*   Enables use of CSVs in `review screen` headless modes.

---

### `jobs`
Centralized management for background workers and persistent tasks (Operation PDF Resilience).

#### `jobs list`
List recent jobs and their current status.
```bash
zotero-cli system jobs list [--limit 50] [--type fetch_pdf|discover_citations]
```

#### `jobs retry`
Reset failed jobs back to `PENDING` state.
```bash
zotero-cli system jobs retry --all
# OR
zotero-cli system jobs retry --job-id 123
```

#### `jobs run`
Starts the background worker to process pending jobs in the queue.
```bash
zotero-cli system jobs run [--limit 10]
```
