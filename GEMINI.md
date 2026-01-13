# Gemini Workspace Context

This document preserves the context, memory, and task history of the `zotero-cli` project development session.

## Persona & Guidelines
**Role:** Interactive CLI Agent specializing in Software Engineering.
**Council:** Dr. Vance (Research), Argentis (Config), Vitruvius (Process), Pythias (Python), Valerius (Quality), Sullivan (Docs).

## Project Overview: `zotero-cli`
A "Systematic Review Engine" CLI tool to import, manage, and screen research papers in Zotero libraries.

**Key Technologies:** Python 3.8+, `requests`, `rich`, `pytest`.

## Accomplished Tasks

### Phase 7: SLR Professionalization (The "Dr. Vance" Suite) - [SESSION ACTIVE]
*   **[COMPLETED] Bug Fix: Infinite Loop in TUI Tests:**
    *   Resolved a critical memory leak/infinite loop in `TuiScreeningService` where `Prompt.ask` interacted with `MagicMock` consoles.
    *   Improved robustness of TUI input handling with `StopIteration` and `EOFError` catching.
    *   Updated `tests/test_tui.py` with complete mock side effects.
*   **[COMPLETED] Audit Sanitization & Migration (`migrate`):**
    *   *Service:* `MigrationService`.
    *   *Command:* `migrate`.
    *   *Standard:* Upgraded all audit notes to **SDB v1.1**.
    *   *Compliance:* Automatically removes legacy `signature` fields and standardizes `agent` to `zotero-cli`.
    *   *Verification:* Added `tests/test_migration.py`.
*   **Infrastructure:**
    *   Added `update_note` support to `ZoteroGateway` and `ZoteroAPIClient`.
*   **Documentation:**
    *   Updated `README.md` and `docs/SLR_FEATURES.md` with PRISMA reporting and Migration standards.
*   **Automated PRISMA Reporting (`report`):**
    *   *Service:* `ReportService`.
    *   *Feature:* Parses Standardized Decision Blocks (SDB) to generate PRISMA 2020 screening statistics.
    *   *Output:* Rich CLI tables and rejection breakdown.
*   **Audit Snapshot (`freeze`):**
    *   *Service:* `SnapshotService`.
    *   *Feature:* Creates immutable JSON snapshots of collections including all child items (notes/attachments).
    *   *Resilience:* Implemented integrity checks and partial success reporting.
*   **Bulk Metadata Lookup (`lookup`):**
    *   *Service:* `LookupService`.
    *   *Feature:* Fetches and formats metadata for lists of Zotero keys into Markdown, CSV, or JSON.
*   **Interactive Screening (`screen` / `decision`):**
    *   *Service:* `ScreeningService`.
    *   *Schema:* Upgraded to **SDB v1.1** (audit_version, persona, phase, reason_code list).
    *   *TUI:* Interactive "Tinder-for-Papers" interface using `rich` for rapid screening.
    *   *CLI:* `decision` command now supports `--persona` and `--phase`.
    *   *Audit Trail:* Automatically creates machine-readable JSON notes for every decision.
*   **Infrastructure:**
    *   Patched `ZoteroGateway` and `ZoteroAPIClient` with `create_note` support.
    *   Added `rich` dependency for TUI/formatting.
*   **Documentation:**
    *   Full `README.md` refactor highlighting the SLR Workflow and Mermaid diagrams.
    *   Detailed technical specs in `docs/SLR_FEATURES.md`.
*   **Quality & Hygiene:**
    *   **Coverage:** Boosted to **87%** (Green).
    *   **Infrastructure Coverage:** `zotero_api.py` reached **90%**.
    *   **TUI Coverage:** `tui.py` reached **87%**.
    *   **Migration Coverage:** `migration_service.py` reached **99%**.
    *   **Purge:** Deleted 15 legacy scripts from `src/` to `legacy_scripts/`.

### Phase 6: Release Engineering (v0.3.0)
*   **Versioning:** Bumped to `v0.3.0`.
*   **Metadata:** Enriched `pyproject.toml` with PyPI fields.

### Phase 5: Refactoring & Quality
*   **Rename:** Repository renamed to `zotero-cli`.
*   **Testing:** Migrated to `pytest`.

## Backlog & Roadmap

### Phase 7 (Part 2): Audit Intelligence
*   **[COMPLETED] Automated PRISMA Reporting (`report`):** One-click generation of screening statistics.
*   **[COMPLETED] SDB v1.1 Upgrade:** Strict schema for audit notes including persona and phase.
*   **[COMPLETED] Migration Tool (`migrate`):** Standardize legacy notes and remove PII (`signature`).
*   **Smart Filtering (`find`):** Advanced querying by audit note content.
*   **Visualization:** Integration with `mmdc` for PRISMA flowchart export.
*   **Refactoring:** Move `legacy_scripts/` to a proper tool-independent folder if still needed.

## Current State
*   **Version:** `v0.4.0`.
*   **Quality:** 80% Test Coverage (Pytest).
*   **Status:** Feature-complete for core SLR screening workflow.
