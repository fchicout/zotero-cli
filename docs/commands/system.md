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