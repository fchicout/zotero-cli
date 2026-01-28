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
Create a full backup of the entire library (System Scope).
Produces a `.zaf` (Zotero Archive Format) file, which is a ZIP archive (LZMA compressed) containing `manifest.json` and `data.json`.

**Usage:**
```bash
zotero-cli system backup --output "full_backup_2026.zaf"
```

**Parameters:**
*   `--output`: (Required) Path to save the backup file.

---

### `restore`

Restore items from a `.zaf` archive.

*Note: Currently in development. Functionality placeholder.*



**Usage:**

```bash

zotero-cli system restore --file "backup.zaf" --dry-run

```



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
