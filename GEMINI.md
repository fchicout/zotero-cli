# Gemini Workspace Context

This document preserves the context, memory, and task history of the `zotero-cli` project development session.

## Persona & Guidelines
**Role:** Interactive CLI Agent specializing in Software Engineering.
**Council:** Dr. Vance (Research), Argentis (Config), Vitruvius (Process), Pythias (Python), Valerius (Quality), Sullivan (Docs).

## Project Overview: `zotero-cli`
A "Systematic Review Engine" CLI tool to import, manage, and screen research papers in Zotero libraries.

**Key Technologies:** Python 3.10+, `requests`, `rich`, `pytest`.

## Accomplished Tasks (Session: 2026-01-13)

### Phase 8: The v1.0.0 Marathon
*   **[RELEASE] v1.0.12:**
    *   **Fix:** Resolved `400 Bad Request` in `update_item_collections` by removing redundant `version` in JSON payload.
    *   **Fix:** Implemented automatic retry on `412 Precondition Failed` for collection movement, ensuring robustness in concurrent environments.
    *   **Verification:** Successfully validated `decide` subcommand for LLM-agent use cases.
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

## Roadmap & Backlog (Post-v1.0.0)

### 🧠 Intelligence (Dr. Vance)
*   [ ] **AI-Assisted Screening:** Implement `analyze suggest` using local LLMs to rank papers against protocol criteria.
*   [ ] **Synthesis Matrix:** Implement `analyze synthesis` to generate Paper-vs-Concept CSVs.

### 🛠 Architecture (Pythias)
*   [ ] **CLI Framework Migration:** Refactor `argparse` to `Typer` or `Click` for better maintainability.
*   [ ] **Persistent Config:** Support `~/.config/zotero-cli/config.toml` to replace strict Env Var dependency.

### 🛡 Quality (Valerius)
*   [ ] **Integration Sandbox:** Set up a live Zotero Group for daily end-to-end regression tests (detect API drift).
*   [ ] **Coverage 90%:** Target specific command handlers for unit isolation.

### ⚙️ Operations (Argentis)
*   [ ] **Semantic Release:** Automate version bumping based on git commit messages.
*   [ ] **PyPI Publishing:** Automate `pip` release.

### 📚 Documentation (Sullivan)
*   [ ] **MkDocs Site:** Publish `docs/` to GitHub Pages.
*   [ ] **Cookbook:** Create a "Recipes" section for complex workflows.

## Current State
*   **Version:** `v1.0.11`.
*   **Quality:** 82% Test Coverage (Green).
*   **Status:** Stable, Feature-Rich, High Performance.