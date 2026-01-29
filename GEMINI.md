# Gemini Workspace Context

This document preserves the context, memory, and task history of the `zotero-cli` project development session.

## Persona & Guidelines
**Role:** Interactive CLI Agent specializing in Software Engineering.

**Lead Team: The Py-Council of Six (High-Quality Python Development)**
*   **Pythias** (Lead Architect): SOLID, Type-Safety, Pythonic Rigor.
*   **Valerius** (Quality): Test Pyramid, 80%+ Coverage, Zero-Failure.
*   **Argentis** (Config): SemVer 2.0.0, Repository Hygiene, Traceability.
*   **Gandalf** (Secure Runner): Hardened Environments, Dependency Security.
*   **Sullivan** (Docs): Cognitive Clarity, Mermaid Visualization.
*   **Vitruvius** (Process): Deterministic CI/CD, The Golden Path.

**Scientific Advisor:**
*   **Dr. Silas:** Research Methodology, Bibliographic Rigor, Kitchenham/Wohlin Standards.

**Modus Operandi:**
We follow **[The Argentis Protocol](@gem-ctx/knowledge/PATTERNS.md#pattern-the-argentis-protocol-code-hygiene--lifecycle)** for all repository operations.

**Quality Assurance:**
All development must strictly adhere to **[The Valerius Protocol](@gem-ctx/knowledge/PATTERNS.md#pattern-the-valerius-protocol-quality-gate)**.
- **Criteria:** 100% Pass / >80% Coverage / Zero Mypy Errors.

## Team Activation Protocol (Workflow Accelerators)
To switch context instantly, use these trigger phrases:

*   **"Bring the council on"** -> Loads `@gem-ctx/teams/ARCH_MGMT.md`
    *   *Action:* Reads Backlog & Architect Inbox.
*   **"Activate Dev Squad"** -> Loads `@gem-ctx/teams/DEV_SQUAD.md`
    *   *Action:* Reads Dev Inbox & Source Code.
*   **"Call the QA Force"** -> Loads `@gem-ctx/teams/QA_FORCE.md`
    *   *Action:* Reads QA Inbox & runs `pytest`.

## Project Overview: `zotero-cli`
A "Systematic Review Engine" CLI tool to import, manage, and screen research papers in Zotero libraries.

### Dual-Domain Architecture
1.  **The Engine (Management):** Direct manipulation of the Zotero database (items, collections, tags, storage).
2.  **The Protocol (SLR):** Advanced workflow support for Systematic Literature Reviews (Kitchenham/Wohlin).

## Rigid Feature Set (SLR Conformance)
(See [ROADMAP.md](ROADMAP.md) for execution state and release planning)

| SLR Phase | CLI Implementation | Status |
| :--- | :--- | :--- |
| **Search & Collect** | `import arxiv`, `import file (RIS/BibTeX/CSV)` | [DONE] |
| **Title/Abstract Screening** | `slr screen` (TUI), `slr decide` (CLI), `slr load` | [DONE] |
| **Full-Text Screening** | `slr decide --phase full_text --evidence "..."` | [DONE] |
| **Data Extraction** | `slr extract` (TUI + Export) | [DONE] |
| **Synthesis & Reporting** | `report prisma`, `report snapshot`, `slr graph` | [DONE] |

**Key Technologies:** Python 3.10+, `requests`, `rich`, `pytest`.

## Accomplishments (Session: 2026-01-27)

### Phase 22: SDB Management & Core Hygiene
*   **[CENTRALIZATION]** Moved team files to \`@gem-ctx/teams/\`.
*   **[VERIFIED] Issue #51 (Purge Unification):** Unified destructive logic under \`PurgeService\`. Added \`item purge\` and \`collection purge\` commands. 90%+ coverage.
*   **[VERIFIED] Issue #57 (Versioning):** Added \`--version\` and injected version into all help headers.
*   **[VERIFIED] Issue #63 (Groups UX):** Fixed missing group names and added \`system switch\` context switching.
*   **[VERIFIED] Issue #59 (SDB Identity):** Implemented robust JSON parsing for SDB notes to prevent duplicate entries.
*   **[VERIFIED] Issue #60 (SDB CRUD):** Added \`slr sdb\` sub-commands for \`inspect\`, \`edit\`, and \`upgrade\`.
*   **[VERIFIED] Issue #61 (Implicit Inclusion):** Refactored TUI/CLI to skip redundant criteria prompts for inclusion votes.
*   **[VERIFIED] Issue #62 (CSV Adapter):** Added column mapping (\`--col-*\`) to \`slr load\` for arbitrary CSV schemas.

## Current State

*   **Version:** \`v2.3.0\`
*   **Quality:** 100% Pass Rate. Coverage maintained at **80%** floor, with critical services (\`Purge\`, \`SDB\`) >90%.
*   **Status:** **STABILIZED & ENHANCED**

## Next Actions (Immediate)
1.  **Feature:** Implement Issue #56 (SDB-Aware Listing).
2.  **Feature:** Implement Issue #55 (Auto-Move on Load).
3.  **Release:** Final push and tag \`v2.3.0\`.

