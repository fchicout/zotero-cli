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

## Accomplished Tasks (Session: 2026-01-16)

### Phase 12: v2.0 Architecture & The Great Reorganization
*   **[RELEASE] v1.2.0:** Tagged and released stable version with fix for Issue #17 and #21.
*   **[ARCH] Workflow-Centric Tree:** Refactored the command hierarchy into logical namespaces: `item`, `collection`, `review`, `tag`, `maint`, and `system`.
*   **[FEAT] Full CRUD Support:** Added foundational API and CLI support for collection creation, deletion, renaming, and bulk tag purging.
*   **[FEAT] Smart Identifiers:** Implemented name-based resolution for collection management commands.
*   **[FEAT] Deep Delete:** Added `--recursive` flag to collection deletion with verbose per-item logging.
*   **[FEAT] Metadata Expansion:** Added `--abstract` support to `item update` and positional key support to `item inspect`.
*   **[UX] System Diagnostics:** Grouped environment and group discovery under `system info` and `system groups`.
*   **[FIX] Dependency Bugs:** Patched `UnpaywallAPIClient` and `MetadataAggregator` initialization errors.
*   **[GUARD] Legacy Routing:** Implemented transparent redirection for v1.x commands with deprecation warnings.

## Current State

*   **Version:** `v2.0.0-dev` (Foundation Complete).
*   **Quality:** 86% Test Coverage. All new CRUD and search paths verified.
*   **Status:** Transitioning to Workflow-Centric architecture.

## Backlog (Prioritized)
*   **Issue #27 (Docs):** Documentation Sprint (Sullivan) - Align README/Guides with v2.0 namespaces.
*   **Issue #18 (Feat):** Implement `review audit` command.
*   **Issue #19 (Feat):** Implement `report screening` generator.
*   **Issue #24 (Arch):** Complete remaining CRUD CLI wrappers (Item move cleanup/Item create generic).
