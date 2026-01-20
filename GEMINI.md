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

## Project Overview: `zotero-cli`
A "Systematic Review Engine" CLI tool to import, manage, and screen research papers in Zotero libraries.

**Key Technologies:** Python 3.10+, `requests`, `rich`, `pytest`.

## Accomplishments (Session: 2026-01-20)

### Phase 17: Usability & Configuration (v2.1)
*   **[FEAT] Interactive Wizard (Issue #28):** Implemented a comprehensive `init` command with:
    *   Prompts for all `ZoteroConfig` fields (Zotero, Semantic Scholar, Unpaywall).
    *   Real-time credential verification against the Zotero API.
    *   Improved TUI using `rich` for better user experience.
*   **[TEST] Quality Assurance:** Added unit tests for the `init` wizard, achieving 100% pass rate.
*   **[QUALITY] Valerius Review:** Evolved tests to cover user overrides, overwrite scenarios, and edge cases (I/O errors). Fixed a `TypeError` in `rich` console usage.
*   **[DOCS] Documentation:** Created `docs/commands/init.md` and updated `USER_GUIDE.md` and `Getting Started` tutorials.
*   **[OPS] Process Hardening:** Standardized the GitHub workflow (assigning/closing issues via `gh`).

## Accomplishments (Session: 2026-01-19)

### Phase 16: Roadmap Definition (v2.1 - v2.2)
*   **[PLANNING] Infrastructure Hardening:**
    *   **Issue #28 (Init):** Defined Interactive Configuration Wizard.
    *   **Issue #30 (Offline):** Defined High-Performance SQLite Reader Mode.
    *   **Issue #31 (Local API):** Defined Local HTTP Adapter (`--backend local`).
*   **[PLANNING] Advanced Workflows:**
    *   **Issue #29 (Checkout/Check-in):** Designed "Storage Offloading" workflow using Source ID tracking.
    *   **Issue #32 (Enrichment):** Designed Retroactive CSV Import for multi-researcher SDB injection.
    *   **Issue #33 (Purge):** Designed maintenance command for batch cleaning of notes/attachments.
*   **[OPS] Repository Hygiene:** Standardized GitHub labels using the "Golden Set" taxonomy across all issues.

### Phase 15: Stable Release (v2.0.0)
*   **[RELEASE] v2.0.0 Stable:** Published the official stable release.

## Current State

*   **Version:** `v2.0.0` (Stable)
*   **Quality:** 100% Unit Test Pass in CI. 100% Quad-Gate pass locally.
*   **Status:** **PLANNING v2.1**

## Next Actions (Immediate)
1.  **Usability:** Implement Issue #28 (`init` wizard).
2.  **Infrastructure:** Implement Issue #30 (`--offline` mode) and #31 (Local API).
3.  **Workflow:** Implement Issue #29 (`move` checkout/check-in) and #32 (CSV Import).