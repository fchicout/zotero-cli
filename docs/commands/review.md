# Command: `review`

The `review` command group handles the Systematic Literature Review (SLR) workflow, including screening, decision recording, and state synchronization.

## Verbs

### `screen`
Interactive Screening Interface (TUI) for title and abstract screening.

**Usage:**
```bash
zotero-cli review screen --source "Target Collection" --include "Included" --exclude "Excluded"
```

**Features:**
*   **Auto-Skip:** Items with existing decision tags (`rsl:phase:*`, `rsl:include`, `rsl:exclude`) are automatically filtered out of the queue to prevent re-screening.
*   **State Tracking:** Can optionally track progress in a local CSV to resume offline.

**Parameters:**
*   `--source`: (Required) Collection name or key to screen.
*   `--include`: (Required) Target collection for items marked as 'Include'.
*   `--exclude`: (Required) Target collection for items marked as 'Exclude'.
*   `--file`: Optional CSV file for bulk decisions (Headless mode).
*   `--state`: Optional local CSV file to track/persist screening state.

---

### `decide` (Alias: `d`)
Record a single decision for an item via the command line.

**Usage:**
```bash
zotero-cli review decide --key "ITEMKEY" --vote "INCLUDE" --code "RELEVANT" --reason "Matches all criteria"
```

**Parameters:**
*   `--key`: (Required) Zotero Item Key.
*   `--vote`: (Required) `INCLUDE` or `EXCLUDE`.
*   `--code`: (Required) Short code for the decision (e.g., `NOT_LLM`, `RELEVANT`).
*   `--reason`: Optional text description of the reason.
*   `--source`: Optional source collection key.
*   `--target`: Optional target collection key.
*   `--agent-led`: Optional flag if the decision was made by an AI/Agent.
*   `--persona`: Optional name of the agent/persona making the decision.

---

### `audit`
Programmatically verify if a collection is 'Submission Ready'. It checks for identifiers, PDF attachments, and valid screening notes.

**Usage:**
```bash
zotero-cli review audit --collection "Screened Papers" --verbose
```

**Validation Rules:**
1.  **DOI / arXiv ID**: Every item must have a unique identifier.
2.  **Title & Abstract**: Metadata must be complete.
3.  **PDF Attachment**: Every item must have at least one imported PDF.
4.  **Screening Note**: Every item must have a valid JSON screening note (SDB v1.1).

---

### `migrate`
Migrate audit notes to newer schema versions.

**Usage:**
```bash
zotero-cli review migrate --collection "My Review"
```

**Parameters:**
*   `--collection`: (Required) Collection name or key.
*   `--dry-run`: Show changes without applying them to Zotero.

---

### `sync-csv`
Recover or synchronize a local CSV state file from Zotero screening notes. Useful for restoring a lost `.csv` state from the Source of Truth (Zotero).

**Usage:**
```bash
zotero-cli review sync-csv --collection "Included" --output "recovered_state.csv"
```

**Parameters:**
*   `--collection`: (Required) Collection name or key.
*   `--output`: (Required) Path where the CSV will be saved.
