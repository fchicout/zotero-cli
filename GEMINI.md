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

## Accomplished Tasks (Session: 2026-01-15)

## Accomplished Tasks (Session: 2026-01-15)

### Phase 11: Backlog Reconciliation & Systematic Mapping Operations
*   **[CLOSED] Issue #13 (Docs):** Synchronized all v1.1.0+ commands in `README.md` and `USER_GUIDE.md`. Defined `report snapshot` JSON contracts.
*   **[CLOSED] Issue #20 (Feat):** Added `--top-only` flag to `list items` command. Implemented `/top` endpoint support in `ZoteroAPIClient`. Achieved 100% test coverage for the feature.
*   **[CLOSED] Issue #8 (Ops):** Verified and closed `sync-csv` state recovery task.
*   **[CLEANUP] Repo Hygiene:** Deleted legacy scripts (`recover_screening_state.py`, `transform_inventory.py`), data dumps, and temporary `issue*.md` files.
*   **[NEW] Quality Tooling:** Implemented `tests/infra/test_doc_consistency.py` to programmatically verify documentation coverage of CLI commands.
*   **[FIX] Issue #17 (Bug):** Identified and patched argument order bug in `manage move`. Created workaround for `decide` command movement failure.
*   **[OPS] arXiv Finalization:** Resolved data drift (Set theory violation) in `raw_arXiv`. Generated final audit CSVs for Included (375) and Excluded (173) sets.
*   **OPS] ScienceDirect Finalization:** Successfully reconciled 1379 items. Recovered 33 audit notes and adjusted 7 items to 'Included' based on re-evaluation.
*   **[FIX] CLI Robustness:** Hardened `sync-csv` and `inspect` commands to handle items with null titles or non-JSON notes gracefully.

## Current State

*   **Version:** `v1.2.0` (Ready for Release).
*   **Research (ScienceDirect):** 1379/1379 items screened and verified.
*   **Research (arXiv):** 100% Finalized and Synced.
*   **Quality:** 86% Test Coverage. Automated Doc-Check active.
*   **Status:** Stable with known bug in `decide` (Issue #17).

## Backlog (Prioritized)
*   **Issue #18 (Feat):** Implement `audit` command to detect incomplete screening (missing notes).
*   **Issue #19 (Feat):** Implement `report screening` generator (Markdown/PRISMA statistics).
*   **Issue #21 (UX):** Improve `decide` (aliases) and `move` (auto-source) command inference.
