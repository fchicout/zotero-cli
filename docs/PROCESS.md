# The Golden Path v2.1: Development Protocol

> **"The Machine That Builds The Machine"**
> This document defines the strict, deterministic process for evolving `zotero-cli`.

## Phase A: Definition (The Intent)
**Trigger:** A new GitHub Issue is selected.

1.  **Ingest & Assign:**
    *   Assign issue to `fchicout`.
    *   Label appropriately (bug, enhancement, refactor).
2.  **The Council Session (Planning):**
    *   **Elena:** Checks User/Team impact.
    *   **Pythias:** Checks Architecture/SOLID.
    *   **Argentis:** Checks Config/Versioning.
    *   **Valerius:** Defines the Test Strategy.
    *   **Output:** A bulleted **Action Plan**.
3.  **User Ratification:**
    *   Present Plan to User.
    *   **STOP.** Do not proceed without explicit "Proceed".

## Phase B: Preparation (The Setup)
**Trigger:** User Approval.

4.  **Branching:**
    *   Create feature branch: `git checkout -b feat/<issue-id>-<slug>` (or `fix/`, `chore/`).
5.  **Test Harness (Red Light):**
    *   Write the *failing* integration or unit test that reproduces the bug or validates the feature.
    *   Verify it fails.

## Phase C: Execution (The Loop)
**Trigger:** Failing Test established.

6.  **Atomic Implementation:**
    *   Write the minimum code to satisfy the test.
    *   Adhere to PEP8 (Ruff) and Type Hints (Mypy).
7.  **The High-Integrity Hexa-Gate:**
    *   Must pass ALL six before committing:
        1.  `ruff check . --fix` (Linting & Style) — **enforced automatically** by the `pre-commit` hook (`.pre-commit-config.yaml`)
        2.  `mypy .` (Type Safety) — **enforced automatically**, same hook
        3.  `bandit -r src/` (Security SAST) — **enforced automatically**, same hook
        4.  `safety check` (Vulnerability Audit) — manual/CI-only (network access required)
        5.  `pytest tests/unit` (Logic) — **enforced automatically** on `git push` (pre-push hook)
        6.  `pytest tests/integration` / `tests/e2e` (Iron Gauntlet - Workflow) — manual/CI-only (live credentials required; never run autonomously by an agent — see `CLAUDE.md`)

    Run `pre-commit install --hook-type pre-commit --hook-type pre-push` once (see `README.md`) to activate 1–3 and 5. This turns the Hexa-Gate from a checklist a human has to remember into something that either ran and passed or didn't let the commit/push happen.
8.  **Green Commit:**
    *   `git commit -m "type(scope): description (Issue #ID)"`
    *   *Repeat Phase C for each logical unit of the feature.*

## Phase D: Integration (The Seal)
**Trigger:** Feature complete and Hexa-Gate passing.

9.  **Cognitive & Privacy Audit:**
    *   **Complexity:** Run `ruff check --select C901` (Complexity < 10).
    *   **Hygiene:** Enforce "Clean Root Policy" (Move artifacts to `data/`).
    *   **Secrets:** Manual sweep for hardcoded keys or PII leaks.
10. **Documentation Sync:**
    *   **Sullivan** updates:
        *   `README.md` (if CLI args changed).
        *   `docs/commands/*.md` and `docs/help_specs/*.md`.
        *   Mermaid Diagrams (if flow changed).
    *   Run `pytest tests/docs` to catch structural drift (missing/orphaned doc entries) before merging.
    *   For a deliberate whole-tree sweep (not a single-issue PR's own slice) — release prep, batch doc cleanup — follow `docs/DOC_CONSISTENCY_PROTOCOL.md` instead of relying on memory.
10. **Merge:**
    *   Merge branch into `develop` / `main`.
11. **Close Issue:**
    *   `gh issue close <id>`.

## Phase E: Release (The Shipment)
**Trigger:** Milestone Completion or Critical Hotfix.

12. **Version Bump:**
    *   Update `pyproject.toml` version.
    *   Update `src/zotero_cli/__init__.py`.
13. **Changelog:**
    *   Update `CHANGELOG.md`.
14. **Tag & Build:**
    *   `git tag vX.Y.Z`
    *   `python -m build`
15. **GitHub Release:**
    *   `gh release create vX.Y.Z dist/* --generate-notes`

---
*Ratified by The Council of Six (Jan 2026)*
