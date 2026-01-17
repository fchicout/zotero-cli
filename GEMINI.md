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

## Accomplishments (Session: 2026-01-17)

### Phase 13: Test Reorganization & Coverage Restoration
*   **[ARCH] Test Reorganization:** Split tests into `unit`, `e2e` (renamed from integration), and `docs` categories.
*   **[FEAT] Test Runner Script:** Created `scripts/test_runner.sh` to support categorized execution and combined coverage.
*   **[QUALITY] Coverage Restoration:** Verified total coverage at **81%**.
    *   Resolved coverage gaps in `infra/canonical_csv_lib.py` (boosted to 100%) and `infra/repositories.py` (boosted to 75%).
*   **[BUGFIX] Test Failures:** Fixed 2 failing unit tests in `system normalize` and path errors in E2E tests after reorganization.
*   **[QUALITY] Zero Tolerance Pass:** Achieved 100% Green status across Ruff (lint) and Mypy (types) after manual fixes for 14 remaining errors.
*   **[PURGE] Legacy Liquidation:** Deleted monolithic `client.py` and legacy `paper2zotero` artifacts. Decomposed logic into services.

### Phase 14: Quality Dashboard (Issue #7)
*   **[INGEST] Issue #7:** Assigned to `fchicout`. Council session completed.
*   **[PLAN] Action Plan:** Create `scripts/generate_badges.py` to automate quality visualization in README.md.

## Current State

*   **Version:** `v2.0.0-rc1` (Release Candidate)
*   **Quality:** 100% Test Pass (244 tests across Unit/E2E/Docs). Zero Mypy Errors. Zero Ruff Errors.
*   **Coverage:** **81% Total**.
    *   *Finding:* The suspected 34% drop was likely due to incomplete test runs or missing coverage scopes in previous sessions. Current audit confirms 81% when running the full suite.
*   **Status:** **READY FOR FINAL RELEASE.**

## Next Actions (Immediate)
1.  **Final Quality Check:** Run full Quad-Gate using `scripts/test_runner.sh all true`.
2.  **Version Release:** Bump version to `2.0.0` and finalize documentation.
3.  **Audit Feature:** Implement Issue #18 (Audit Command) as the first v2.1 feature.