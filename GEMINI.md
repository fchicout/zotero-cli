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

## Accomplishments (Session: 2026-01-16)

### Phase 12: The Golden Path Implementation
*   **[PROCESS] Establishment of Golden Path v2.1:** Codified in `docs/PROCESS.md`. Mandatory Quad-Gate (Ruff/Mypy/Unit/E2E).
*   **[CLOSED] Issue #16 (Feat):** Implemented TUI Fast-Skip. Uses tag matching (`rsl:phase:*`) to bypass already-screened items. Verified via Real-API E2E.
*   **[CLOSED] Issue #27 (Feat):** Implemented System Backup/Restore. Supports full library and scoped collection backup to `.zaf` (LZMA compressed ZIP).
*   **[CLOSED] Issue #15 (Arch):** Standardized CSV Schema. Implemented Canonical Research CSV mapping for IEEE, Springer, and BibTeX. Added `system normalize` command.
*   **[CLOSED] Issue #14 (Ops):** Implemented `review prune`. Enforces mutual exclusivity between Included/Excluded sets using robust DOI/arXiv matching.
*   **[CLOSED] Issue #9 (Ops):** Implemented `analyze shift`. Detects collection drift between snapshots.
*   **[QUALITY] Zero Mypy Tolerance:** Resolved ALL logic errors and warnings in source code. Achieved 100% Green Mypy report.
*   **[BUGFIX] CLI Registration:** Resolved critical issue where Noun commands (`import`, `system`, `collection`) were not registering due to missing imports in `main.py` and missing decorators.
*   **[VERIFICATION] Iron Gauntlet:** All 21 tests (Unit + Real-API E2E) passed successfully.

## Current State

*   **Version:** `v2.0.0-rc1` (Release Candidate)
*   **Quality:** 100% Test Pass. Zero Mypy Errors. Zero Ruff Errors.
*   **Coverage Crisis:** Total coverage dropped from **81% to 34%**.
    *   *Root Cause (Suspected):* The "Deep Clean" included legacy files (`infra/zotero_api.py`, `client.py`, `repositories.py`) in the calculation. These were previously hidden or excluded.
*   **Status:** **HALTED.** Coverage regression investigation required before v2.0.0 Final.

## Next Actions (Immediate)
1.  **Coverage Audit:** Identify why coverage plummeted. Check if previous 81% was scoped only to `core/`.
2.  **Test Expansion:** Increase unit/integration tests for legacy `infra/` and `client.py` methods.
3.  **Final Release:** Bump version to `2.0.0` and tag once Coverage is restored/explained.