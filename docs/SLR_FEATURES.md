# SLR Professionalization Suite: Technical Specifications

**Status:** Backlog
**Target Version:** v0.4.0
**Context:** Enhancing `zotero-cli` to support rigorous Systematic Literature Review (SLR) workflows (Kitchenham/Wohlin).

---

## 1. Feature: Interactive Screening Mode (`screen`)

**Goal:** Increase screening velocity (Title/Abstract phase) by 5-10x by eliminating UI context switching and automating the "Move + Note" workflow.

### User Experience (UX)
```bash
zotero-cli screen --source "raw_arXiv" --include "screening_arXiv" --exclude "excluded_arXiv"
```
*   **Interface:** Terminal UI (TUI).
*   **Display:**
    *   **Header:** `[Progress: 15/548]`
    *   **Title:** (Bold, Cyan) "Large Language Models for Cyber Security..."
    *   **Meta:** `2024` | `Smith et al.` | `arXiv:2405.xxxxx`
    *   **Abstract:** Text wrapped to terminal width. Keywords (LLM, Security) optionally highlighted.
*   **Controls:**
    *   `[i]`: Include. -> Prompts: `Criteria Code? (Default: IC1):`
    *   `[e]`: Exclude. -> Prompts: `Criteria Code? (e.g., EC1, EC4):`
    *   `[s]`: Skip (Move to end of queue).
    *   `[q]`: Quit.

### Technical Implementation
*   **State Management:** Fetch batch of items (e.g., 20).
*   **Audit Logging (CRITICAL):**
    *   On decision, create a Child Note for the item.
    *   **JSON Schema:**
        ```json
        {
          "action": "screening_decision",
          "decision": "INCLUDE|EXCLUDE",
          "code": "IC1",
          "timestamp": "2026-01-12T14:00:00Z",
          "agent": "zotero-cli"
        }
        ```
*   **Zotero Actions:**
    1.  Create Note (API call).
    2.  Patch Item `collections` list (Remove from Source, Add to Target).

---

## 2. Feature: Automated PRISMA Reporting (`report`)

**Goal:** Real-time visibility into the SLR funnel and audit trail validation.

### User Experience (UX)
```bash
zotero-cli report --collections "raw_arXiv,screening_arXiv,excluded_arXiv" --output "prisma_stats.md"
```

### Technical Implementation
*   **Aggregator:**
    *   Fetch all items from specified collections.
    *   Fetch all child notes.
*   **Parser:**
    *   Identify notes matching the `screening_decision` JSON schema.
    *   Ignore human-written notes.
*   **Metrics:**
    *   `Total Records`: Count items.
    *   `Decisions`: Count unique items with decision notes.
    *   `Conflict Check`: Identify items with *multiple* conflicting decisions (e.g., one Note says INCLUDE, another EXCLUDE).
    *   `Breakdown`: Group by `code` (EC1: 12, EC2: 4, IC1: 45).
*   **Output:** Markdown table.

---

## 3. Feature: Bulk Metadata Lookup (`lookup`)

**Goal:** Generate "Selected Studies" tables for the final paper/synthesis without manual copy-pasting.

### User Experience (UX)
```bash
zotero-cli lookup --keys "KEY1,KEY2,KEY3" --fields "arxiv_id,title,year,url" --format table
# OR from file
zotero-cli lookup --file "selected_keys.txt" --format json
```

### Technical Implementation
*   **Input:** List of Zotero Item Keys.
*   **Fetcher:** `gateway.get_item(key)` (Parallelized).
*   **Formatter:**
    *   `table`: Markdown table (for `GEMINI.md` reports).
    *   `csv`: For Excel/Sheets analysis.
    *   `json`: For programmatic piping.

---

## 4. Feature: Smart Filtering (`find`)

**Goal:** Query the *audit trail*, not just the metadata. "Why did we include this?"

### User Experience (UX)
```bash
# Find included papers missing a DOI
zotero-cli find --collection "screening_arXiv" --has-note "IC1" --missing "doi"

# Find papers excluded due to "Survey" (EC4)
zotero-cli find --collection "excluded_arXiv" --note-contains "EC4"
```

### Technical Implementation
*   **Filter Engine:**
    *   Level 1: Item Metadata (has PDF, missing DOI, year < 2020).
    *   Level 2: Audit Trail (Note content parsing).
*   **Performance:** Requires fetching children (notes), so this operation is expensive. Needs progress bar.

---

## 5. Feature: Snapshot / Freeze (`freeze`)

**Goal:** Reproducibility. Proving the state of the review at the time of submission.

### User Experience (UX)
```bash
zotero-cli freeze --collection "raw_arXiv" --output "slr_snapshot_v1.json"
```

### Technical Implementation
*   **Dumper:**
    *   Iterate all items.
    *   Embed children (notes/attachments metadata) directly into the parent object.
*   **Format:** Single monolithic JSON file (or JSONL).
*   **Utility:** Can be used to "restore" or "replay" the screening process (e.g., if we migrate to a new Zotero library).
