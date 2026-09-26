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
        4.  Dependency vulnerability audit — `pip-audit` on the locked runtime dependencies, run by CI (network access required). Locally: `uv export --locked --no-dev --no-hashes --no-emit-project -o /tmp/req.txt && uvx --from pip-audit==2.10.1 pip-audit -r /tmp/req.txt --no-deps --disable-pip`
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
14. **Tag & Publish:**
    *   Merge the version-bump PR, then `git tag -a vX.Y.Z -m "Release vX.Y.Z"` on `main` and push the tag.
    *   The tag triggers `.github/workflows/release.yml`: it builds the Linux/Windows binaries, creates the GitHub Release, then publishes the sdist/wheel to PyPI as `zotero-command-line`. The PyPI step refuses a tag that doesn't match `pyproject.toml`'s version.
    *   Check that the release has its binaries and that the new version is on https://pypi.org/project/zotero-command-line/.

---
*Ratified by The Council of Six (Jan 2026)*

## Destructive commands

Every command that deletes, or changes many items at once, follows one policy (Issue #378):

1. **Preview by default.** It shows what it would do and changes nothing until `--execute`. Commands that predate 3.0 and still apply by default (`storage checkout`, `system restore`) get `--dry-run`/`--execute` and a deprecation warning in 3.1, and switch to preview-by-default in 4.0 ([COMPATIBILITY.md](COMPATIBILITY.md), #462). `item delete` names one item, like `rm FILE`: it deletes without `--execute`.
2. **Confirm bulk permanent deletes.** With `--execute`, a bulk delete asks for confirmation. `--yes` skips the question. Without a terminal and without `--yes`, it refuses with exit status 2 instead of guessing (`cli/safety.py`).
3. **`--force` only ever skips a prompt.** It never means "apply".
4. **Resolve targets unambiguously first.** A collection name that matches several collections is refused (#381).
5. **Never delete more than asked for.** Items also filed outside the target are kept unless the user opts in (`--include-shared`). A step that depends on an earlier one (deleting a source after copying it) runs only if the earlier step fully succeeded.
6. **Honor versions.** Deletes send the object's own version; if it changed since, nothing is deleted and the command fails (#384).
7. **Review every new delete path.** `tests/unit/test_destructive_paths.py` fails when a new file calls a delete method, until the path has a gate and is added to its reviewed list.
