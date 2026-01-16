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

**Modus Operandi (The Argentis Protocol):**
1.  **Atomic Commits:** Every logical change (feature, refactor, doc) must be a separate commit.
2.  **Strict Semantic Versioning:** Commit messages must follow Conventional Commits (feat, fix, refactor, docs, chore, test).
3.  **Traceability:** No "WIP" commits. Code must be runnable/testable at every commit.
4.  **Verification:** Verify status and diffs before committing.

## Project Overview: `zotero-cli`
A "Systematic Review Engine" CLI tool to import, manage, and screen research papers in Zotero libraries.

**Key Technologies:** Python 3.10+, `requests`, `rich`, `pytest`.

## Accomplished Tasks (Session: 2026-01-16)

### Phase 11: Backlog Reconciliation & Systematic Mapping Operations
*   **[CLOSED] Issue #19 (Feat):** Implemented `report screening` command. Generates full Markdown reports with PRISMA statistics and Mermaid diagrams.
*   **[CLOSED] Issue #24 (Arch):** Implemented Full CRUD Repository Pattern. Split monolithic gateway into specialized repositories (Item, Collection, Tag, Note, Attachment).
*   **[CLOSED] Issue #18 (Feat):** Implemented `review audit` command. Detects items missing DOI, PDFs, or SDB v1.1 screening notes. Integrated into the new Pre-Flight Protocol. (Assigned to: fchicout).
*   **[NEW] Pre-Flight Protocol:** Formalized `tests/integration/test_slr_workflow.py` as a mandatory E2E regression suite (Iron Gauntlet).
*   **[ARCHITECTURAL PURGE] v2.0 Transition:**
    *   Removed `handle_legacy_routing`.
    *   Deleted `manage_cmd.py` and `maint_cmd.py` (Functionality re-homed to Noun-Verb structure).
    *   Modularized documentation in `docs/commands/`.
*   **[FIX] PDF Upload:** Resolved 400 error in attachment registration by aligning with Zotero v3 API specs.
*   **[FIX] Duplicate Detection:** Refactored `DuplicateFinder` to use IDs and added arXiv ID as a definitive match criteria.
*   **[CLOSED] Issue #13 (Docs):** Synchronized all v1.1.0+ commands in `README.md` and `USER_GUIDE.md`. Defined `report snapshot` JSON contracts.
*   **[CLOSED] Issue #20 (Feat):** Added `--top-only` flag to `list items` command. Implemented `/top` endpoint support in `ZoteroAPIClient`. Achieved 100% test coverage for the feature.
*   **[CLOSED] Issue #8 (Ops):** Verified and closed `sync-csv` state recovery task.
*   **[CLEANUP] Repo Hygiene:** Deleted legacy scripts (`recover_screening_state.py`, `transform_inventory.py`), data dumps, and temporary `issue*.md` files.
*   **[NEW] Quality Tooling:** Implemented `tests/infra/test_doc_consistency.py` to programmatically verify documentation coverage of CLI commands.
*   **[FIX] Issue #17 (Bug):** Fully refactored `ScreeningService` to delegate item movement to `CollectionService`, resolving the `decide` command failure and removing code duplication (PR #22).
*   **[CLOSED] Issue #21 (UX):** Implemented `decide` alias (`zotero-cli d`) and strict auto-source inference for item movement. Logic fails safely on ambiguity (PR #23).
*   **[OPS] arXiv Finalization:** Resolved data drift (Set theory violation) in `raw_arXiv`. Generated final audit CSVs for Included (375) and Excluded (173) sets.
*   **OPS] ScienceDirect Finalization:** Successfully reconciled 1379 items. Recovered 33 audit notes and adjusted 7 items to 'Included' based on re-evaluation.
*   **[FIX] CLI Robustness:** Hardened `sync-csv` and `inspect` command to handle items with null titles or non-JSON notes gracefully.
*   **[FEAT] Report Dashboard:** Implemented `report status` with Rich progress bars and stats table (Issue #12).
*   **[UX] Decide Presets:** Added `--short-paper`, `--not-english`, `--is-survey`, `--no-pdf` flags to `decide` command for rapid screening.
*   **[REFACTOR] CLI Structure:** Registered `screen` and `decide` as top-level commands for better ergonomics.

## Current State

*   **Version:** `v2.0.0-dev`
*   **Research (ScienceDirect):** 1379/1379 items screened and verified.
*   **Research (arXiv):** 100% Finalized and Synced.
*   **Quality:** 100% Test Pass (216 tests + Expanded Iron Gauntlet E2E). Coverage: 81%.
*   **Status:** Pre-Release (Gate: Clear GitHub Issue Backlog).

## Backlog (Prioritized)
*   **Issue #27 (Feat):** Implement `system backup/restore` using `.zaf`.
*   **Issue #3 (Infra):** Implement Quality Gates (ruff/mypy) in CI.
*   **Issue #16 (Feat):** Refine TUI to skip items with existing SDB notes (v1.1 verification).
