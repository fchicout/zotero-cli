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

*   **"Bring the council on"** -> Loads `.team/ARCH_MGMT.md`
    *   *Action:* Reads Backlog & Architect Inbox.
*   **"Activate Dev Squad"** -> Loads `.team/DEV_SQUAD.md`
    *   *Action:* Reads Dev Inbox & Source Code.
*   **"Call the QA Force"** -> Loads `.team/QA_FORCE.md`
    *   *Action:* Reads QA Inbox & runs `pytest`.

## Project Overview: `zotero-cli`
A "Systematic Review Engine" CLI tool to import, manage, and screen research papers in Zotero libraries.

### Dual-Domain Architecture
1.  **The Engine (Management):** Direct manipulation of the Zotero database (items, collections, tags, storage).
2.  **The Protocol (SLR):** Advanced workflow support for Systematic Literature Reviews (Kitchenham/Wohlin).

## Rigid Feature Set (SLR Conformance)
| SLR Phase | CLI Implementation | Status |
| :--- | :--- | :--- |
| **Search & Collect** | `import arxiv`, `import file (RIS/BibTeX/CSV)` | [DONE] |
| **Title/Abstract Screening** | `slr screen` (TUI), `slr decide` (CLI), `slr load` | [DONE] |
| **Full-Text Screening** | `slr decide --phase full_text --evidence "..."` | [DONE] |
| **Data Extraction** | (Future scope: Structured JSON extraction forms) | [PLANNED] |
| **Synthesis & Reporting** | `report prisma`, `report snapshot`, `slr graph` | [DONE] |

**Key Technologies:** Python 3.10+, `requests`, `rich`, `pytest`.

## Accomplishments (Session: 2026-01-22)



### Phase 20: Release v2.3 Preparation & MSI Finalization

*   **[BUMP] Version 2.3.0:** Formally bumped project version in `pyproject.toml`.

*   **[FIX] MSI Versioning Compliance:** Patched `.github/workflows/release.yml` to sanitize semantic version tags for WiX compatibility (stripping non-numeric suffixes).

*   **[DOCS] Changelog v2.3.0:** Consolidated all v2.3 improvements and semantic consolidation into `CHANGELOG.md`.

*   **[QUALITY] Valerius Final Gate:** Re-verified the entire suite (272 tests) with 81% coverage, zero Ruff errors, and zero Mypy errors.



## Current State

*   **Version:** `v2.3.0`
*   **Quality:** 100% Pass Rate (272 tests). Global coverage: **81%**.
*   **Status:** **RELEASED**

## Next Actions (Immediate)
1.  **Infrastructure:** Implement Issue #30 (`--offline` mode).
2.  **Workflow:** Implement Issue #29 (`move` checkout/check-in).
3.  **Refactoring:** Refactor API `GET /items` to use native Zotero pagination.
