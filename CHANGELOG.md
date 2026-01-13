# Changelog

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
