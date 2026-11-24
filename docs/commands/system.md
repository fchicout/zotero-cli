# Command: `system`

The `system` command handles administrative tasks, information, and global library maintenance.

## Verbs

### `info`
Display the zotero-cli version, Python version and platform, and the active configuration (config path, library ID and type, whether API keys are set). Include this output in bug reports. `zotero-cli --version` prints just the version.

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

### `check`
Runs lightweight, read-only connectivity/credential checks against Zotero, Semantic Scholar, Unpaywall, and PubMed/NCBI.

**Usage:**
```bash
zotero-cli system check
```

---

### `selftest`
Checks offline that this installation works: converts a small embedded PDF to text (the code path of `item export --as md`) opens a SQLite database (used by `--offline`), and translates a LaTeX accent with the bundled `bxc` library (used by BibTeX import), and formats a reference in a bundled citation style (used by `--as bibliography`). Needs no configuration or network; exits 1 if any check fails.

**Usage:**
```bash
zotero-cli system selftest
```

---

### `demo-sandbox`
Creates a temporary collection populated with mock papers so you can try the item, collection and report commands without touching your real library. Requires a live (non-`--offline`) Zotero connection.

**Usage:**
```bash
zotero-cli system demo-sandbox
zotero-cli system demo-sandbox --name "My Sandbox"
zotero-cli system demo-sandbox --clean
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
Creates a complete, self-contained backup archive (`.zaf`) of your entire Zotero library or a specific collection, including all metadata and every attachment file Zotero stores (PDFs, web snapshots, files downloaded from a URL, images in notes). Every attachment is mathematically verified using SHA-256 checksums.

**Usage:**
```bash
zotero-cli system backup --output "full_backup_2026.zaf"
# a group library, named on the call (a global option, so it goes before the command)
zotero-cli --group 6629576 system backup --output "group_backup_2026.zaf"
```

**Parameters:**
*   `--output`: (Required) Path to save the backup file.
*   `--group GROUP` (global option): back up this group library (id or URL) instead of the configured one; `--user` backs up your personal library. The command says which library it is reading when it starts.

---

### `verify`
Performs a deep integrity check on a `.zaf` archive. Validates all internal JSON structures and re-calculates checksums for every attachment to ensure 100% data fidelity. It shows the library the archive came from and checks the counts the archive records (items, files, collections) against what it holds, so a cut file is noticed.

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
zotero-cli system restore --file "backup.zaf" [--dry-run | --execute] [--yes]
```

**Parameters:**
*   `--file`: (Required) Path to the .zaf archive.
*   `--dry-run`: Simulates the restore without making any changes. Mutually exclusive with `--execute`.
*   `--execute`: Applies the restore. Mutually exclusive with `--dry-run`. Without it only a preview is shown (Issue #462).
*   `--yes`: Skips the question asked when the archive was taken from a different library (personal or group) than the one being restored into. Archives record their library from format 1.2 on.

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
zotero-cli system jobs list [--limit 50] [--type fetch_pdf|discover_citations] [--format table|json|csv|ndjson|keys]
```

#### `jobs retry`
Reset a failed job back to `PENDING` state, by its ID (`system jobs list` shows it).
```bash
zotero-cli system jobs retry 123
```

#### `jobs run`
Starts the background worker to process pending jobs in the queue.
```bash
zotero-cli system jobs run [--count 10] [--type fetch_pdf] [--watch]
```
