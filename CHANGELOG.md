# Changelog

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
