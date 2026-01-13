# SLR Professionalization Suite: Technical Specifications

**Status:** Active / v0.4.0-dev
**Target Version:** v0.4.0
**Context:** Enhancing `zotero-cli` to support rigorous Systematic Literature Review (SLR) workflows (Kitchenham/Wohlin).

---

## 0. The Standardized Decision Block (SDB) v1.1

All screening decisions are recorded as Zotero Child Notes containing a JSON block.

### Schema
```json
{
  "audit_version": "1.1",
  "decision": "accepted|rejected",
  "reason_code": ["IC1", "IC2"],
  "reason_text": "Optional descriptive text",
  "timestamp": "ISO-8601 UTC",
  "agent": "zotero-cli|zotero-cli-tui|zotero-cli-agent",
  "persona": "researcher_name",
  "phase": "title_abstract|full_text",
  "action": "screening_decision"
}
```

### Migration Policy
Legacy notes (v1.0 or unversioned) are migrated to v1.1 using the `migrate` command:
1.  **Remove `signature`:** Persona information must reside in the `persona` field.
2.  **Standardize `agent`:** Tool identity is strictly `zotero-cli` (or variants).
3.  **List-based Codes:** `code` or string `reason_code` are converted to lists.

---

## 1. Feature: Interactive Screening Mode (`screen`) [COMPLETED]

**Goal:** Increase screening velocity (Title/Abstract phase) by 5-10x.

### Controls
*   `[i]`: Include. -> Prompts: `Criteria Code? (Default: IC1):`
*   `[e]`: Exclude. -> Prompts: `Criteria Code? (e.g., EC1, EC4):`
*   `[s]`: Skip.
*   `[q]`: Quit.

---

## 2. Feature: Automated PRISMA Reporting (`report`) [COMPLETED]

**Goal:** Real-time visibility into the SLR funnel.

### Implementation
*   Parses SDB v1.1 notes.
*   Generates Mermaid.js source for PRISMA 2020 diagrams.
*   Renders diagrams to PNG/SVG using `mermaid-py`.

---

## 3. Feature: Bulk Metadata Lookup (`lookup`) [COMPLETED]

---

## 4. Feature: Smart Filtering (`find`) [PLANNED]

---

## 5. Feature: Snapshot / Freeze (`freeze`) [COMPLETED]
