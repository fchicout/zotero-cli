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

## Project Overview: `zotero-cli`
A "Systematic Review Engine" CLI tool to import, manage, and screen research papers in Zotero libraries.

**Key Technologies:** Python 3.10+, `requests`, `rich`, `pytest`.

## Accomplished Tasks (Session: 2026-01-14)

### Phase 11: Backlog Reconciliation & Architectural Refinement
*   **[CLOSED] Issue #2 (Bug):** Validated `ZeroDivisionError` in `report snapshot` as non-reproducible (logic guards confirmed).
*   **[MERGED] Issue #4 (Infra):** Implemented `BaseAPIClient` with `tenacity` retries. Refactored Unpaywall, Semantic Scholar, and Crossref clients to use unified transport.
*   **[MERGED] Issue #8 (Ops):** Implemented `manage sync-csv` to recover screening state from Zotero notes. **(Training: Feature Branch Workflow)**.
*   **[NEW] Backlog:**
    *   **Issue #12:** `report status` (Markdown Dashboard) registered.
    *   **Issue #13:** Documentation Hygiene (Critical) registered.
*   **Governance:** Established strict "Feature Branch -> PR -> Merge" workflow.

### Phase 9: Persistent Configuration & Robustness (Previous)
*   **[RELEASE] v1.1.0:**
    *   **Feature:** Implemented **Persistent Configuration** via `config.toml`.
    *   **Standards:** Adhered to XDG Base Directory Specification (`~/.config/zotero-cli/`).
    *   **Precedence:** Established clear config hierarchy: CLI Flags > Environment Variables > Config File.
    *   **Robustness:** Fixed `400 Bad Request` and implemented `412` concurrency retries for item movement.
    *   **Quality:** Maintained **80%** global test coverage with 177 passing tests.
    *   **Docs:** Updated `README.md` and `USER_GUIDE.md` with configuration instructions.

### Phase 8: The v1.0.0 Marathon
*   **[RELEASE] v1.0.12:**
    *   **Fix:** Resolved `400 Bad Request` in `update_item_collections` by removing redundant `version` in JSON payload.
    *   **Fix:** Implemented automatic retry on `412 Precondition Failed` for collection movement.
*   **[RELEASE] v1.0.11 (Final Stable):**
    *   **Architecture:** Full SOLID Refactor. Decoupled `ZoteroAPIClient` (Repository) from `ZoteroHttpClient` (Transport).
    *   **Features:**
        *   **Context:** Added Global `--user` flag for Personal Library override.
        *   **Diagnostics:** Added `zotero-cli info`.
        *   **Discovery:** Added `zotero-cli inspect`.
        *   **Performance:** Optimized `manage move` from O(N) to O(1) using direct Key lookup.
        *   **Bulk Screening:** Added `screen --file decisions.csv` for headless batch processing.
    *   **Quality:**
        *   Test Coverage boosted to **82%**.
        *   Added `tests/test_zotero_api_failures.py` for comprehensive error handling.
    *   **Documentation:** Fully updated `README.md` and `USER_GUIDE.md`.

## Operational Protocols

### SOP-008: Improvement Proposals
*   **Requirement:** Every code enhancement or feature must be registered as a GitHub Issue.
*   **Template:** Use the "Improvement Proposal" template (`.github/ISSUE_TEMPLATE/improvement_proposal.md`).
*   **Enforcement:** Argentis will veto any PR/Commit that does not reference an Issue ID (#XX).
*   **Traceability:** Commits must follow Conventional Commits: `feat: <desc> (#XX)`.

## Roadmap & Backlog (GitHub Managed)

All future work is now tracked centrally at [fchicout/zotero-cli/issues](https://github.com/fchicout/zotero-cli/issues).

### 🚀 Active Backlog (Synced 2026-01-14)

| ID | Category | Title | Priority | Status |
| :--- | :--- | :--- | :--- | :--- |
| **#8** | `[OPS]` | **manage sync-csv: Recover State** | High | **[MERGED]** |
| **#3** | `[ADR-018]` | **Quality Gates: Static Analysis in CI** | High | **[NEXT]** |
| **#5** | `[AI]` | analyze suggest: Local LLM Screening | High | Pending |
| **#10** | `[DOCS]` | Move artifacts to Ops_Governance | Medium | Pending |
| **#9** | `[OPS]` | Collection Shift Detection | Medium | Pending |
| **#6** | `[AI]` | analyze synthesis: Synthesis Matrix | Medium | Pending |
| **#7** | `[QUALITY]` | Quality Dashboard: Automated Badges | Low | Pending |
| **#4** | `[INFRA]` | BaseAPIClient for Metadata Providers | **Critical** | **[MERGED]** |
| **#2** | `[BUG]` | ZeroDivisionError in SnapshotService | **Critical** | **[CLOSED]** |
| **#13** | `[DOCS]` | Documentation Hygiene & report snapshot | **Critical** | Pending |
| **#12** | `[FEAT]` | report status: Markdown Dashboard | High | Pending |



## Current State

*   **Version:** `v1.1.0`.
*   **Research:** 510/1313 ScienceDirect items screened.
*   **Quality:** 80% Test Coverage. SOP-008 enforced.
*   **Status:** Stable. Ready for Phase 11: Backlog Reconciliation.
