# SLR Professionalization Suite: Technical Specifications

**Status:** Active / v1.2.0
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
Legacy notes (v1.0 or unversioned) are migrated to v1.1 using the `manage migrate` command:
1.  **Remove `signature`:** Persona information must reside in the `persona` field.
2.  **Standardize `agent`:** Tool identity is strictly `zotero-cli` (or variants).
3.  **List-based Codes:** `code` or string `reason_code` are converted to lists.

---

## 1. Feature: Interactive Screening Mode (`screen`) [COMPLETED]

**Goal:** Increase screening velocity (Title/Abstract phase) by 5-10x.
Includes a TUI mode and a single-shot `decide` CLI command.

---

## 2. Feature: Automated PRISMA Reporting (`report prisma`) [COMPLETED]

**Goal:** Real-time visibility into the SLR funnel.
*   Parses SDB v1.1 notes.
*   Generates Mermaid.js source for PRISMA 2020 diagrams.

---

## 3. Feature: Bulk Metadata Lookup (`analyze lookup`) [COMPLETED]

---

## 4. Feature: Recovery & Sync (`manage sync-csv`) [COMPLETED]
**Goal:** Recover the screening state from Zotero SDB notes back to local CSV files if the local database is lost or for external synthesis.

---

## 5. Feature: Snapshot / Audit Trail (`report snapshot`) [COMPLETED]
**Goal:** Create an immutable, deep JSON snapshot of a collection for auditing and reproducibility.
