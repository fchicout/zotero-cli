# Gemini Workspace Context

This document preserves the context, memory, and task history of the `zotero-cli` (formerly `paper2zotero`) project development session.

## Persona & Guidelines
**Role:** Interactive CLI Agent specializing in Software Engineering.
**Mandates:**
*   Strict adherence to project conventions, style, and structure.
*   Idiomatic changes; understanding local context.
*   Proactive implementation including tests.
*   **Security:** NEVER expose API keys in code or commits. Use `.gitignore` and environment variables.
*   **Workflow:** Understand -> Plan -> Implement -> Verify (Tests) -> Finalize.

## Project Overview: `zotero-cli`
A CLI tool to import research papers into Zotero from various sources (arXiv, BibTeX, RIS, CSV) and manage Zotero libraries (metadata, tags, attachments).

**Key Technologies:** Python 3.8+, `requests`, `zotero-api`, `unittest`.

## Accomplished Tasks

### Phase 1: Core Functionality & CLI
*   **Move Item:** Implemented `move` command to transfer items between collections.
    *   *Service:* `CollectionService`.
    *   *Gateway:* `update_item_collections`.
*   **Audit Collection:** Implemented `audit` command to check for missing metadata (ID, title, abstract, PDF).
    *   *Service:* `CollectionAuditor` (parallelized with `ThreadPoolExecutor`).
    *   *Model:* `ZoteroItem`.
*   **Duplicate Detection:** Implemented `duplicates` command (DOI/Title matching).
    *   *Service:* `DuplicateFinder`.
*   **Citation Graph:** Implemented `graph` command to generate Graphviz DOT files.
    *   *Service:* `CitationGraphService`.
    *   *Architecture:* `MetadataAggregatorService` combining `CrossRefAPIClient` and `SemanticScholarAPIClient`.

### Phase 2: Metadata Enrichment & Semantic Scholar
*   **Metadata Aggregation:** Created `MetadataAggregatorService` to merge data from multiple providers using heuristics (e.g., longest abstract, most authors).
*   **Semantic Scholar:** Integrated `SemanticScholarAPIClient` with API key support (`x-api-key`) and rate limiting.
*   **Unpaywall:** Integrated `UnpaywallAPIClient` to fetch PDF URLs (`pdf_url` field added to `ResearchPaper`).
*   **Bug Fixes:** Handled null references in Semantic Scholar responses.

### Phase 3: Tag Management
*   **Tag Service:** Implemented `TagService` for listing, adding, removing, renaming, and deleting tags.
*   **CLI:** Added `tag` command with subcommands (`list`, `add`, `remove`, `rename`, `delete`).
*   **Gateway:** Added `get_tags`, `get_items_by_tag`, and `get_item` to `ZoteroGateway`.

### Phase 4: Attachment Management

## Backlog & Roadmap

### Phase 7: SLR Professionalization (The "Dr. Vance" Suite)
*   **Bulk Metadata Lookup (`lookup`):**
    *   *Goal:* Generate synthesis tables directly from a list of Keys.
    *   *Inputs:* Key list (CSV/Arg) + Requested Fields.
    *   *Outputs:* Formatted Table (Markdown/CSV).
*   **Interactive Screening Mode (`screen`):**
    *   *Goal:* Internalize the screening loop (Tinder for Papers).
    *   *Features:* Terminal UI, single-keypress decision (I/E), auto-move to collection, auto-attach JSON rationale note.
*   **Automated PRISMA Reporting (`report`):**
    *   *Goal:* One-click generation of the "Screening Report".
    *   *Features:* Parse JSON notes, count decisions, generate PRISMA flow stats, export Markdown summary.
*   **Smart Filtering (`find`):**
    *   *Goal:* Advanced querying of audit data.
    *   *Features:* Search by JSON note content (e.g., "Show all excluded by EC1").
*   **Snapshot/Freeze (`freeze`):**
    *   *Goal:* Audit verification.
    *   *Features:* Dump full collection state to local JSON file for point-in-time proof.
*   **Infrastructure:** Implemented `upload_attachment` in `ZoteroAPIClient` (handling Zotero's 3-step upload protocol).
*   **Service:** Created `AttachmentService` to identify missing PDFs, fetch URLs via Unpaywall, download, and upload to Zotero.
*   **CLI:** Added `attach-pdf` command.
*   **Verification:** Unit tests for `AttachmentService` created and passed. All associated files are now correctly tracked by Git.

### Security Incident & Remediation
*   **Incident:** API keys were accidentally committed to `setup_env.sh` and pushed.
*   **Remediation:**
    *   Scrubbed `setup_env.sh` from git history using `git filter-branch`.
    *   Added `setup_env.sh` to `.gitignore`.
    *   Force-pushed cleaned history to remote.
    *   **User Action Required:** Rotate Zotero and Semantic Scholar keys.

## Current State
*   **Version:** `v0.3.0` (Released).
*   **Identity:** `zotero-cli` (Module: `zotero_cli`).
*   **Quality:** 80% Test Coverage (Pytest).
*   **Status:** PyPI-ready metadata configured. Binaries building on GitHub.

## Accomplished Tasks

### Phase 6: Release Engineering (v0.3.0)
*   **Versioning:** Bumped to `v0.3.0`.
*   **Metadata:** Enriched `pyproject.toml` with PyPI fields (classifiers, keywords, license).
*   **Changelog:** Updated `README.md` with release notes.
*   **Tagging:** Pushed `v0.3.0` tag to trigger release workflow.

### Phase 5: Refactoring & Quality (Operation Identity Alignment)
*   **Rename:** Renamed repository and internal package from `paper2zotero` to `zotero-cli`/`zotero_cli`.
*   **Testing:**
    *   Migrated test suite from `unittest` to `pytest`.
    *   Refactored `test_client.py` and `test_cli.py` to use fixtures.
    *   Expanded coverage for `zotero_api.py`, `client.py`, and `main.py` (CLI subcommands).
    *   Fixed Python 3.10 compatibility issue in `arxiv_query_parser.py`.
*   **CI/CD:** Updated GitHub Actions to run `pytest` with coverage.

### Phase 4: Attachment Management