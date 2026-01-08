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
*   **Version:** `v0.2.0+` (Feature-rich).
*   **Tests:** Unit tests cover all services and infrastructure (mocked). CI/CD should now be passing with the latest fixes.
*   **Documentation:** `README.md` updated with all new commands and Changelog.

## Next Steps / Pending
1.  **Tag Auto-Automation:** Implement auto-tagging based on search queries or metadata rules (e.g., "Tag all papers by 'Hinton' with 'DL'").
2.  **Notes & Annotations:** Support for adding/editing notes in Zotero items.
3.  **Search:** Implement a generic search command across the library.
4.  **Sync/Merge:** Advanced duplicate merging (currently only detection is supported).
5.  **Refinement:** Verify `attach-pdf` robustness in real-world scenarios (handling large files, timeouts, different PDF sources).

## Important Configuration
*   **Environment Variables:**
    *   `ZOTERO_API_KEY`
    *   `ZOTERO_TARGET_GROUP`
    *   `SEMANTIC_SCHOLAR_API_KEY`
    *   `UNPAYWALL_EMAIL`