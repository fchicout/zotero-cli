# DOC-SPEC: system restore

## 1. Classification
- **Level:** 🔴 DESTRUCTIVE (Library Overwrite/Reconstruction)
- **Target Audience:** SysAdmin / Advanced User

## 2. Logic Flow (Visual Synthesis)
```mermaid
graph TD
    A["Start System Restore"] --> B["Validate .zaf Archive Integrity"]
    B --> C["Read config.toml for Target Environment"]
    C --> D{"Dry Run?"}
    D -- "Yes" --> E["Display Summary of Items to be Restored"]
    D -- "No" --> F[""Purge Current Library State (If required")"]
    F --> G["Reconstruct Collections and Items via API"]
    G --> H["Upload PDF Attachments to Cloud/Local Storage"]
    H --> I["Restore child notes and metadata"]
    E --> J["End: Restore Process Summary"]
    I --> J
```

## 3. Synopsis
Reconstructs an entire Zotero library or specific collections from a previously created Zotero Archive Format (`.zaf`) file.

## 4. Description (Instructional Architecture)
The `system restore` command is the counterpart to `system backup`. It allows you to re-materialize research data from an archive into a living Zotero library. This is crucial for disaster recovery, migrating between accounts, or reverting a library to a known good state after a major error. 

The command carefully parses the `.zaf` archive, identifies all bibliographic records and files, and uses the Zotero API to recreate the library structure exactly as it was when the backup was taken. This includes the recreation of folders (collections) and the re-attachment of physical PDF files. The `--dry-run` flag is an essential safety feature that allows you to see exactly what will be created or modified before the operation begins.

## 5. Parameter Matrix
| Flag / Parameter | Type | Description | Ergonomic Note |
| :--- | :--- | :--- | :--- |
| `--dry-run` | Boolean | Simulate restore | Mutually exclusive with `--execute`. |
| `--execute` | Flag | Apply the restore | Mutually exclusive with `--dry-run`. Without it only a preview is shown (Issue #462). |
| `--file` | String | Input .zaf file | Required. |
| `--yes` | Flag | Do not ask before restoring into a different library than the archive came from | Archives made since 4.2 record their library (personal or group, and its id). If it is not the library the command is about to write to, the preview warns, and `--execute` asks first (without a terminal it refuses with exit 2 unless `--yes` is given). |

## 6. Scenario-Based Examples (Cognitive Anchors)
### Scenario: Recovering from an accidental library deletion
**Problem:** I've accidentally deleted a large set of folders in Zotero and I need to restore them from last week's backup.
**Action:** `zotero-cli system restore --file "backup_2024_01_01.zaf" --dry-run`
**Result:** The CLI shows exactly which items and folders will be recreated, allowing me to proceed with confidence.

### Scenario: Applying a restore after reviewing the plan
**Problem:** I've checked the `--dry-run` output and I'm ready to actually restore.
**Action:** `zotero-cli system restore --file "backup_2024_01_01.zaf" --execute`
**Result:** The archive is restored into the library.

## 7. Cognitive Safeguards
- **Notes keep their tags** (manual and automatic) as well as their text.
- **Stand-alone notes and files:** a note or a file that was filed in a collection without a parent item comes back as a top-level item in the same collections (matched by their text or file when restoring again). Anything the archive holds that is not restored (for example an item whose parent could not be restored, or the images embedded in notes) is listed under `Not restored` in the summary instead of being skipped silently; it does not make the command fail.
- **Restoring twice is safe:** collections are matched by name and parent, items by DOI or title, notes by their text and attachments by their file (md5, or the file name when the existing attachment has no md5), so a second run into the same library creates nothing. The summary shows how many attachments were skipped as already there.
- **Common Failure Modes:** Attempting to restore a `.zaf` file that is corrupted or from a different account context that lacks matching permissions. A backup of one library is never restored into another by accident: check the `Warning:` line of the preview. 
- **Safety Tips:** Restore operations can be complex and destructive if the target library already contains data. ALWAYS run with `--dry-run` first to understand the impact of the restore. Without `--execute` nothing is written to your library: you get a preview (`--dry-run` is the explicit spelling).
