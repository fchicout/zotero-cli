# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0-dev] - 2026-01-16

### Added
- **Noun-Verb Architecture:** Completely reorganized the CLI into a logically scoped structure (e.g., `item`, `collection`, `review`).
- **Command: `review audit`:** Programmatic verification of collection completeness (Identifiers, PDFs, Screening Notes).
- **Command: `item pdf attach`:** Support for uploading local files (PDF, PostScript, DVI) with automatic MIME detection.
- **Pre-Flight Protocol:** Mandatory System Integration Test suite (`tests/integration/test_slr_workflow.py`).
- **Modular Documentation:** Detailed documentation for every command noun in `docs/commands/`.
- **Guided Tours:** Narrative-based user stories for common SLR tasks.

### Changed
- **Scoping Fix:** Moved bulk PDF operations from `item` to `collection` namespace.
- **Improved PDF Upload:** Fully aligned with Zotero v3 API specification for reliable multi-step file registration.
- **Test Automation:** Enhanced documentation consistency tests to verify 100% parity between CLI and Markdown.

### Removed
- **Legacy Routing:** Deleted `manage` and `maint` top-level commands and their associated legacy routing logic.

## [1.2.0] - 2026-01-15

### Architecture
*   **Command Pattern:** Refactored the entire CLI router into a registry-based Command Pattern. Logic is now modularized in `cli/commands/`.
*   **Strategy Pattern:** Implemented the Strategy Pattern for paper importers, enabling easier extension for new bibliographic formats.
*   **Dependency Injection:** Introduced `GatewayFactory` to centralize infrastructure creation and decouple commands from concrete implementations.
*   **Centralized Configuration:** Moved all configuration and global state management to `core/config.py`.

### Features
*   **Decide Alias:** Added `d` alias for `decide` command to speed up manual screening.
*   **Smart Move:** `manage move` and `decide` now support auto-inference of the source collection. If an item belongs to exactly one other collection, it is moved from there automatically. Fails safely on ambiguity.
*   **Persistent State:** Added `--state <FILE.csv>` to `screen` command. Researchers can now resume sessions and track local screening decisions across restarts.
*   **Extended Inspection:** Added `--full-notes` to `inspect` command to display untruncated note content (useful for auditing inclusion/exclusion rationale).

### Fixes
*   **Decide Command:** Fixed critical bug where `decide` failed to move items due to logic duplication. Now delegates to `CollectionService`.
*   **Snapshot:** Fixed `ZeroDivisionError` in `report snapshot` when processing empty collections.
*   **Inspect:** Resolved bug where `inspect --raw` failed due to missing `raw_data` attribute in `ZoteroItem`.

### Quality
*   **Mock Isolation:** Enhanced test suite to mock default configuration paths, preventing local developer configs from leaking into test environments.
*   **Regressions:** Maintained 100% pass rate across 180 unit/integration tests.

## [v1.1.0] - 2026-01-13 (Retrospective)
*   **Configuration:** Added persistent configuration via `config.toml` (XDG Specification).
*   **Precedence:** Established CLI Flags > Env > Config File hierarchy.

## [v1.0.12] - 2026-01-13

### Quality
*   **Tests:** Fixed additional edge cases in `CollectionService` tests for move operations.

## [v1.0.10] - 2026-01-13

### Quality
*   **Tests:** Fixed unit tests for `CollectionService` to correctly mock the new `get_item` optimization.

## [v1.0.9] - 2026-01-13

### Performance
*   **Move Command:** Optimized `manage move` to use direct Item Key lookup (O(1)) instead of scanning the entire source collection (O(N)). Huge speedup for large libraries.

## [v1.0.8] - 2026-01-13

### Bug Fixes
*   **Collection Movement:** Improved robustness of `screen` command item movement. Now correctly handles Collection Keys vs Names and avoids unnecessary API calls if collections haven't changed.

## [v1.0.7] - 2026-01-13

### Features
*   **Bulk Screening:** New headless screening mode via CSV import.
    *   Command: `zotero-cli screen --file decisions.csv ...`
    *   Supports distributed team workflows.

## [v1.0.6] - 2026-01-13

### Bug Fixes
*   **Inspect Command:** Fixed attribute mapping for `date` and `authors`.
*   **Imports:** Fixed missing `Console` import in `info` command.

## [v1.0.5] - 2026-01-13

### Features
*   **Global Flag:** Added `--user` flag to force the tool to use the Personal Library, bypassing any active `ZOTERO_TARGET_GROUP`.

## [v1.0.4] - 2026-01-13

### Features
*   **Command:** Added `zotero-cli inspect` for viewing detailed item metadata and children.
*   **UX:** `zotero-cli list items` now filters out nested items (attachments/notes) for a cleaner view.
*   **UX:** `zotero-cli list items` supports case-insensitive partial collection names.

## [v1.0.3] - 2026-01-13

### Features
*   **Info Command:** New `zotero-cli info` command to display diagnostic configuration.
*   **Usability:** Improved collection name resolution with case-insensitive and partial match support.

## [v1.0.2] - 2026-01-13

### Quality
*   **Test Coverage:** Increased to 82% (Green) by adding comprehensive failure scenarios for API wrappers.
*   **Verification:** Verified full CLI command tree functionality.

## [v1.0.1] - 2026-01-13

### Architecture
*   **SOLID Refactor:** Decoupled `ZoteroAPIClient` (Repository) from `ZoteroHttpClient` (Transport).
*   **SRP Compliance:** Extracted HTTP logic, headers, and rate limiting to a dedicated transport layer.

## [v1.0.0] - 2026-01-13

### Major Changes
*   **Command Tree Refactor:** Completely redesigned CLI structure for better usability.
    *   `import` (file, arxiv, manual)
    *   `screen` (TUI)
    *   `report` (prisma, snapshot)
    *   `manage` (tags, pdfs, duplicates, clean, move, migrate)
    *   `analyze` (audit, lookup, graph)
    *   `find` (arxiv)
    *   `list` (collections, groups, items)
*   **Personal Library Support:** Added `ZOTERO_USER_ID` support. Tools now work with both Group and User libraries.
*   **Universal Import:** Unified `import file` command auto-detects `.bib`, `.ris`, and `.csv`.

### Features
*   **List Groups:** New `list groups` command to discover User Group IDs.
*   **List Items:** New `list items` command to inspect collections.
*   **PRISMA Viz:** Integrated `mmdc` (Mermaid CLI) for high-quality flowchart generation.

### Fixes
*   **Concurrency:** Resolved `If-Unmodified-Since-Version` locking issues during batch migration.
*   **TUI:** Fixed infinite loop in test mocks.

### Breaking Changes
*   Removed top-level commands: `bibtex`, `ris`, `springer-csv`, `ieee-csv`, `freeze`, `audit`, `duplicates`, `tag`, `attach-pdf`. These are now subcommands.
