# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### ✨ Features & Improvements
- **Duplicate Detection Parity + Improvements (Issue #152):** `report duplicates` now matches by ISBN in addition to DOI/ArXiv/title, and can scan the whole library instead of specified collections (`--collections` is now optional). Items that don't exactly match anything else are additionally compared via a fuzzy fallback tier (title similarity + publication year within 1 year + at least one shared author last-name/first-initial), the same corroborating-signal approach Zotero Desktop uses — including a distinct `preprint-published-pair` label for a preprint matched against its later published version, a common SLR case Desktop's own algorithm doesn't call out explicitly.
- **`item merge` (Issue #155):** New generic, SLR-independent primitive for merging duplicate items — pick a master and one or more duplicates (found via `report duplicates`), and the command unions their tags/collections, moves notes/attachments onto the master, then permanently deletes the duplicates. Conflicting scalar fields (title, date, DOI, ISBN, URL, abstract) require an explicit per-field choice, no silent "first wins". Preview-only by default; `--execute` (plus confirmation, or `--force`) is required to actually write. This is necessarily a one-way, permanent operation — the Zotero Web API only exposes a hard delete, unlike Zotero Desktop's internal, reversible merge mechanism.
- **Bulk merge plans: `report duplicates --export-plan` + `item merge --from-plan` (Issue #156):** `report duplicates` can now export every found group as an editable plan file (`.csv` opens in a spreadsheet with blank role/reason columns; `.json` additionally embeds each occurrence's full SDB screening history for a richer review UI). Fill in which occurrence is the `MASTER`, which are `MERGE`/`KEEP`, and why, then run `item merge --from-plan <file> --execute` to commit every fully-resolved group in one pass. Completeness is all-or-nothing — a single group missing a decision blocks the *entire* plan, not just that group. The same `MergePlan`/`MergeDecision` dataclasses are meant to be built and consumed directly as Python objects (no file round-trip) by a future SLR-aware caller like Corbenic-SLR.
- **`slr dedupe`: SLR-specific duplicate reconciliation (Issue #157):** New command that reuses `report duplicates`'s detection scoped to the SLR source tree (every `raw_*` collection and its phase subfolders, or a given `--sources` set), and classifies each duplicate group by whether existing SDB screening decisions agree (`MATCHING`/`CONFLICTING`/`UNSCREENED`) — relocating that classification out of `report_cmd.py` into `SDBService.classify_decision_agreement`, now shared by both commands. `MATCHING`/`UNSCREENED` groups get an auto-filled merge decision and can be consolidated with `--execute`; `CONFLICTING` groups (independently-screened copies whose decisions genuinely disagree) are always left untouched — export the plan and resolve them via `item merge --from-plan`. Physical consolidation is delegated entirely to `MergeService`; a richer SDB reconciliation note (folded occurrences' own prior decisions and source collections, via an extended `SLROrchestrator.record_duplicate_resolution`) is written per merge, preserving audit history rather than collapsing it into a flat "merged" note. `slr report prisma --dedupe-source` can now also feed a read-only duplicate count into the PRISMA Identification-stage numbers.

### 🛡️ Quality & Infrastructure
- **Distribution path for library consumers (Issue #154):** Documented the decision in `docs/ARCHITECTURE.md` — `zotero-cli` is not published to PyPI and won't be; a consumer like Corbenic-SLR that needs the `core/` services directly should depend on it via a git dependency pinned to a release tag (`pip install git+https://github.com/fchicout/zotero-cli@vX.Y.Z`, or `[tool.uv.sources]`), which needs zero new release infrastructure since every release already gets a git tag. Also fixed a pre-existing unclosed mermaid code fence in that same doc (the "Data Contracts" section, including this new one, was rendering as part of an unclosed code block).
- **`DuplicateFinder` as a Clean Library API (Issue #153):** `DuplicateFinder.find_duplicates`/`compare_collections` now return typed `DuplicateGroup`/`DuplicateOccurrence` dataclasses instead of ad hoc dicts, and no longer `print()` internally — non-fatal issues (e.g. a named collection that doesn't exist) are collected in `self.warnings` for the caller to surface instead. `MergeService`, the merge-plan dataclasses (#155/#156), and `SLRDedupeService` (#157) were all built to the same standard — typed dataclass returns, no stdout side effects, narrow constructor dependencies — completing the four services this issue covers.
- **README & Help-Text Accuracy Sweep:** Refreshed `README.md` to cover features that existed but weren't documented (BDTD import, `system check`, `system demo-sandbox`, Docker/devcontainer packaging, citation snowballing, RAG); fixed several dead command references left over from prior refactors (`slr validate` → `report audit`, `slr graph`/`slr shift`/`report status`/`report prisma` → their real `slr report <verb>` forms). Fixed two real bugs found in the process: `item list --help`'s description/example referenced SDB filtering flags (`--included`, `--criteria`, `--persona`) that were removed from that command in an earlier refactor (that filtering now lives in `slr list`), and `tag purge`'s runtime deprecation warning pointed to `collection purge --tags`, a command that was never implemented. Also fixed `scripts/generate_badges.py` silently dropping the CI status badges on every regeneration.

## [2.8.1] - 2026-07-19

### ✨ Features & Improvements
- **Deeper Duplicate Analysis (Issue #107):** `report duplicates` now reports which collection each duplicate occurrence came from and whether their SDB screening decisions agree (`MATCHING`/`CONFLICTING`/`UNSCREENED`), plus a `--csv` export flag for audit records.
- **Diagnostic Health Checks (Issue #129):** New `system check` command probes Zotero, Semantic Scholar, Unpaywall, PubMed/NCBI, and the configured LLM/embedding providers, reporting CONNECTED/FAILED/NOT CONFIGURED for each.
- **Onboarding Demo Sandbox (Issue #130):** New `system demo-sandbox` command provisions a temporary collection with 6 mock papers (one pre-seeded with a mock SDB note) so new users can try screening/reporting/RAG commands without touching their real library; `--clean` removes it afterward.
- **Docker / Dev Container / Installer Scaffolding (Issue #131):** Added a root `Dockerfile` (lightweight runtime image packaging the same PyInstaller binary as the standalone releases), `.devcontainer/` for GitHub Codespaces/VS Code, and `install.sh`/`install.ps1` one-line installer scripts fetching the latest release binary.

### 🛡️ Quality & Infrastructure
- **Strict Type Checking (Issue #132):** `mypy`'s `disallow_untyped_defs` is now `true` for `src/` (annotating the ~1050 pre-existing test-function signatures under `tests/` is a separate follow-up, kept lenient via an override for now); fixed all 231 real gaps this surfaced across 69 files.
- **`GatewayFactory` Decomposition:** Split the 941-line, 58-method `GatewayFactory` "God Object" into 5 focused sub-factories (`RepositoryFactory`, `MetadataClientFactory`, `ResolverFactory`, `AIProviderFactory`, `ServiceFactory`); `GatewayFactory` itself is now a thin, fully backward-compatible facade.
- **No More `sys.exit()` in Infra:** Removed all `sys.exit()` calls from gateway construction; invalid configuration (missing credentials, unparseable group URL, unresolved library) now raises a typed `ConfigurationError`, caught cleanly at the CLI boundary.
- **Interface Segregation:** Narrowed `TagService`, `AuditService`, `ExportService`, `CitationGraphService`, `DuplicateFinder`, `SnapshotService`, and `SyncService` off the full `ZoteroGateway` onto the specific narrow repositories (Item/Collection/Tag) they actually use.
- **AI-Ready SDLC Pivot:** Retired the stale Gemini-persona process-doc layer in favor of `CLAUDE.md` + GitHub Issues as the single source of truth; added mechanically-enforced quality gates (pre-commit hooks for ruff/mypy/bandit/pytest) and migrated tooling from pip to `uv`.
- **Documentation Consistency Sweep:** Removed 23 stale doc files describing commands renamed/removed in earlier refactors (`slr reset`/`migrate` → `slr sdb reset`/`upgrade`, `collection duplicates` → `report duplicates`, `find-pdf` → `item pdf`, and others), corrected the README command-reference table's key-verb listings, and fixed `tests/docs` to catch this class of drift going forward (header-row false positive in the Parameter Matrix parser, and new orphan-doc checks for both `docs/help_specs/` and `docs/commands/`).

## [2.7.0] - 2026-05-07

### ✨ Features & Improvements
- **Formal Project Documentation:** Added comprehensive `REQUIREMENTS.md`, `USE_CASES.md`, and `USER_STORIES.md` to the `docs/` directory, establishing a clear functional and user-centric baseline for the project.

### 🛡️ Quality & Infrastructure (The Council Audit)
- **Root Directory Hygiene:** Performed a major cleanup of the project root, moving misplaced data artifacts (`.csv`, `.json`, `.txt`) to the `data/` directory and removing legacy coverage artifacts.
- **Documentation Consolidation:** Synchronized internal architectural notes with user-facing requirements to ensure cognitive clarity across the codebase.

## [2.6.1] - 2026-04-26

### ✨ Features & Improvements
- **SLR Status Dashboard:** Enhanced `slr status` with a new "Tree Total" column and global aggregate rows, providing a 360-degree view of the systematic review funnel across all sources.
- **Traceable Duplicate Auditing:** Implemented forensic duplicate logging; every resolution during system restore is now permanently recorded in SDB Audit Notes for 100% accountability.
- **Dependency Injection Refactor:** Major architectural cleanup of core services using constructor injection, centralized via the `GatewayFactory` for better testability and isolation.
- **Unified Purge Engine:** Consolidated all destructive operations (tag removal, PDF stripping) into a single, high-fidelity `PurgeService` to ensure consistent "Dry Run" and safety checks.

### 🛡️ Quality & Infrastructure (Valerius Protocol)
- **Green State Certification:** Reached a landmark stability milestone with 100% test pass rate, 0 lint/type errors, and 0 warnings.
- **80% Coverage Gate:** Successfully cleared the global 80% code coverage threshold with new unit tests for high-impact SLR commands.
- **Zero-Leak E2E Sentinel:** Integrated a robust `ResourceTracker` in the E2E suite that guarantees remote Zotero resource cleanup even on test failures or crashes.
- **Python 3.14 Modernization:** Hardened the codebase for Python 3.14 compatibility and implemented targeted suppression of legacy library deprecation noise.

## [2.6.0] - 2026-04-21

### ✨ Features & Improvements
- **RAG Verification Engine (Spec v1.1):** Introduced automated integrity checks for semantic search results. Results can now be verified against mandatory academic identifiers (DOI/arXiv) and screening status.
- **Fidelity Integrity Guards:** Enforced high-fidelity JSON serialization in the RAG pipeline. Snippets are now preserved without truncation in `--json` output, ensuring 100% data reliability for citation verification.
- **Citation Key Traceability:** Enhanced the `ZoteroItem` model to automatically extract and verify Citation Keys from the Zotero 'extra' field.
- **Verification CLI:** Added the `--verify` flag to `rag query`, providing real-time feedback on the "verified" status of retrieved context.

### 🛡️ Quality & Infrastructure
- **Restoration Gate:** Established a new safety protocol to verify the integrity of critical research database backups (`.bak_research`) during the test lifecycle.
- **Valerius Protocol Expansion:** Hardened the RAG test suite with exhaustive unit and fidelity tests.
- **Interface Consolidation:** Refactored `RAGService` to use a unified and more flexible ingestion strategy.

## [2.5.0] - 2026-03-14

### ✨ Features & Improvements
- **RAG Core (Issue #93):** Introduced Systematic Knowledge Retrieval. Allows building a local vector store from PDF full-texts and metadata for LLM context injection.
- **BibTeX Engine (Issue #94, #95):** Added direct collection export to `.bib` format. Includes phase-aware screening notes and criteria in the metadata.
- **Universal Item Transfer (Issue #91, #90):** Implemented high-fidelity cross-library move operations. Supports transferring items between personal and group libraries while preserving metadata and unfiled items.
- **Direct DOI Import (Issue #81):** Added `import doi <DOI>` command for instant bibliographic resolution and PDF discovery.
- **Full-Text Resilience:** Integrated `markitdown` for improved PDF-to-Markdown extraction, powering the RAG pipeline.

## [2.4.1] - 2026-01-29

### ✨ Features & Improvements
- **Safe Reset Engine (Issue #52):** Introduced \`slr reset\` command for phase-aware clearing of screening and extraction progress.
- **Granular Purging:** Enhanced \`PurgeService\` to support filtering by reviewer persona and screening phase, ensuring high-fidelity data management.
- **Tag Auto-Cleanup:** Automatic removal of phase-specific tags during reset operations.

## [2.4.0] - 2026-01-29

### ✨ Features & Improvements
- **SDB-Aware Listing (Issue #56):** Enhanced \`list items\` with support for screening database filters (\`--included\`, \`--excluded\`, \`--criteria\`, \`--persona\`, \`--phase\`).
- **Dynamic UX Rendering:** Active SDB filters trigger a specialized table schema showing Decisions, Criteria, and Persona metadata with color-coded status.
- **Auto-Move on Load (Issue #55):** The \`slr load\` command now supports automatic collection movement using \`--move-to-included\` and \`--move-to-excluded\` flags.
- **Improved CSV Matching:** Enhanced \`AuditService\` to handle case-insensitive CSV headers (\`status\`, \`decision\`) for better compatibility with external exports.

## [2.3.0] - 2026-01-22

### ✨ Features & Improvements
- **Semantic CLI Consolidation (Issue #38, #40):** Unified all systematic review commands under the `slr` namespace for improved ergonomics.
- **SLR Protocol Refinement (Issue #48):** Flattened the `slr` command tree (e.g., `slr load`, `slr validate`).
- **SDB v1.2 & Phase Isolation (Issue #49, #50):** Added support for `full_text` screening phase with evidence capture and phase-isolated notes.
- **Retroactive SDB Injection (Issue #32):** New `slr load` command with fuzzy matching for importing external decisions into the library.
- **Pre-flight Environment Checks (Issue #46):** Implemented "Boot Guard" pattern to enforce environment requirements at startup.

### 🛡️ Quality & Infrastructure
- **MSI Installer Support (Issue #45):** Added official Windows MSI installer infrastructure using WiX v4.
- **Hard Coverage Gate (80%):** Successfully reached and enforced the 80% global test coverage threshold.
- **Recursive Deletion (Issue #37):** Refactored collection deletion to be truly recursive, preventing orphaned items.
- **ArXiv DOI Fallback (Issue #35):** Enhanced DOI extraction logic for ArXiv imports using regex on comments and references.
- **Test Hygiene (Issue #36):** Hardened E2E cleanup fixtures to ensure 100% resource reclamation.

## [2.0.0] - 2026-01-17

### 🚀 Major Architectural Shift (v2.0)
- **Service-Oriented Logic:** Completely decomposed the monolithic legacy `client.py` into specialized services (`ImportService`, `AttachmentService`, `CollectionService`).
- **Repository Pattern:** Solidified the persistence layer with a strict Repository Pattern, decoupling business logic from the Zotero API implementation.
- **Legacy Purge:** Successfully "liquidated" all remnants of the `paper2zotero` project name and associated garbage code.

### ✨ Features & Improvements
- **Automated Quality Dashboard:** Implemented `scripts/generate_badges.py` providing real-time quality visualization (Coverage, Lint, Types) in `README.md`.
- **System Maintenance:** Added `system normalize` to convert external CSV formats (IEEE, Springer) into the CLI's Canonical Research Schema.
- **Advanced Operations:** Implemented `review prune` for enforcing mutual exclusivity between collections and `analyze shift` for tracking collection drift.
- **Robust Backup:** Introduced `.zaf` (LZMA-compressed ZIP) system-wide and collection-scoped backup/restore capabilities.

### 🛡️ Quality & Testing
- **The Iron Gauntlet:** Established a comprehensive 221-test suite split into three deterministic categories:
    - `unit`: Fast, isolated logic tests (80% qualitative coverage).
    - `e2e`: Full-stack "Iron Gauntlet" tests against real Zotero API instances.
    - `docs`: Automated consistency checks between CLI help and Markdown documentation.
- **Zero-Tolerance Quality:** Achieved 100% Green status on `ruff check` and `mypy` strict type checking.
- **Automated Test Runner:** Created `scripts/test_runner.sh` for unified, categorized test execution.

### ⚠️ Breaking Changes
- Monolithic `PaperImporterClient` has been removed. Integration must now use `GatewayFactory` to obtain specific services.
- Version `2.0.0` is now the stable baseline for all future systematic review automation.

## [2.0.0-rc1] - 2026-01-16 (Release Candidate)

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
