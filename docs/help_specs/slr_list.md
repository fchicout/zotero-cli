# Subcommand: `slr list`

Lists papers in the SLR funnel based on their status (pending, included, or excluded) and phase. This command identifies funnel bottlenecks and provides a clear view of the audit trail.

---

## 1. New Command Structure
The tool now follows a unified listing pattern for all SLR papers:

### `list pending`
Identifies papers physically in a phase's queue folder but missing an SDB note for that phase.

**Usage:**
```bash
zotero-cli slr list pending [--tree <source>]
```
- **`--tree`**: Optional filter by root collection name or key (e.g., `raw_acm`). If absent, lists all pending papers across every SLR source.

### `list included`
Lists papers that have "Accepted/Included" SDB notes across the entire tree of a source.

**Usage:**
```bash
zotero-cli slr list included [--tree <source>] [--ta] [--ft|--fullscreen] [--qa <threshold>]
```
- **`--ta`**: Filter for Title & Abstract phase.
- **`--ft` / `--fullscreen`**: Filter for Full Text phase.
- **`--qa <threshold>`**: Filter for Quality Assessment phase (defaults to threshold 2.0).

### `list excluded`
Lists papers that have "Rejected/Excluded" SDB notes across the entire tree of a source.

**Usage:**
```bash
zotero-cli slr list excluded [--tree <source>] [--ta] [--ft|--fullscreen] [--qa <threshold>]
```

---

## 2. Enhanced Filtering & Logic
*   **Note-First Truth:** Unlike the physical displacement logic, the `included` and `excluded` commands scan the **entire tree** of a source (Root + all 4 phase subfolders) to find audit notes. This ensures we see the real status regardless of where the paper is physically located.
*   **Phase Aliases:** Supported `--fullscreen` as an alias for the `--ft` (full_text) phase to align with common research terminology.
*   **QA Thresholds:** The `--qa` flag defaults to a threshold of 2.0 but accepts custom values to filter Quality Assessment results based on your protocol's minimum score.
*   **Grouped Output:** Results are automatically sorted and grouped by SLR phase for better readability.

---

## 3. Scenario-Based Examples (ACM Source)
*   **List Pending:** `zotero-cli slr list pending --tree raw_acm`
    *   *Result:* Identifies items awaiting data extraction or those stuck in earlier phases.
*   **List Included (TA):** `zotero-cli slr list included --tree raw_acm --ta`
    *   *Result:* Lists all papers accepted during the Title/Abstract screening phase.
*   **List Excluded (TA):** `zotero-cli slr list excluded --tree raw_acm --ta`
    *   *Result:* Lists papers rejected during Title/Abstract, displaying their specific exclusion codes (e.g., EC1).

---

## Cognitive Safeguards
• Common Failure Modes: Confusing "Pending" (Queue-based) with "Included" (Note-based). Always check `slr status` to see the quantitative breakdown before listing.
• Safety Tips: Use `--tree` frequently to narrow down your focus when dealing with multiple data sources.
