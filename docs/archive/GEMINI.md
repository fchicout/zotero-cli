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

**Modus Operandi:**
We follow **[The Argentis Protocol](@gem-ctx/knowledge/PATTERNS.md#pattern-the-argentis-protocol-code-hygiene--lifecycle)** for all repository operations.

**Quality Assurance:**
All development must strictly adhere to **[The Valerius Protocol](@gem-ctx/knowledge/PATTERNS.md#pattern-the-valerius-protocol-quality-gate)**.
- **Criteria:** 100% Pass / >80% Coverage / Zero Mypy Errors.

## GitHub Integration Mandate
- **Tooling:** Always use the `gh` (GitHub CLI) tool for all GitHub-related interactions (issues, PRs, comments) in the `fchicout/zotero-cli` repository.
- **Reporting:** Register task completed reports as comments in each GitHub Issue immediately after implementation and verification.

## Team Activation Protocol (Workflow Accelerators)
To switch context instantly, use these trigger phrases:

*   **"Bring the council on"** -> Loads `@gem-ctx/teams/ARCH_MGMT.md`
    *   *Action:* Reads Backlog & Architect Inbox.
*   **"Activate Dev Squad"** -> Loads `@gem-ctx/teams/DEV_SQUAD.md`
    *   *Action:* Reads Dev Inbox & Source Code.
*   **"Call the QA Force"** -> Loads `@gem-ctx/teams/QA_FORCE.md`
    *   *Action:* Reads QA Inbox & runs `pytest`.

## Project Overview: `zotero-cli`
A "Systematic Review Engine" CLI tool to import, manage, and screen research papers in Zotero libraries.

### Dual-Domain Architecture
1.  **The Engine (Management):** Direct manipulation of the Zotero database (items, collections, tags, storage).
2.  **The Protocol (SLR):** Advanced workflow support for Systematic Literature Reviews (Kitchenham/Wohlin).

## Rigid Feature Set (SLR Conformance)
(See [ROADMAP.md](ROADMAP.md) for execution state and release planning)

| SLR Phase | CLI Implementation | Status |
| :--- | :--- | :--- |
| **Search & Collect** | `import arxiv`, `import file (RIS/BibTeX/CSV)` | [DONE] |
| **Title/Abstract Screening** | `slr screen` (TUI), `slr decide` (CLI), `slr load` | [DONE] |
| **Full-Text Screening** | `slr decide --phase full_text --evidence "..."` | [DONE] |
| **Data Extraction** | `slr extract` (TUI + Export) | [DONE] |
| **Synthesis & Reporting** | `report prisma`, `report snapshot`, `slr graph` | [DONE] |
| **Knowledge Retrieval** | `slr rag ingest/query/context` | [NEW] |

**Key Technologies:** Python 3.10+, `requests`, `rich`, `pytest`, `markitdown`, `numpy`.
## Accomplishments (Session: 2026-03-18)
### Phase 25: Infrastructure, Metadata & UX Evolution
- **[VERIFIED] Issue #98 (Manual Item Creation):** Added `item add` command.
  - Implemented manual creation via `item add --collection <COL> --title <TITLE>`.
  - Integrated Zotero API template resolver for robust schema compliance.
  - Supported multi-author parsing and custom item types.
- **[VERIFIED] Issue #96 (Core Refactor):** Decomposed monolithic SLR logic into specialized services.
  - Split `CollectionAuditor` into `IntegrityService`, `SnapshotService`, and `CSVInboundService`.
  - Implemented Strategy pattern for item matching in CSV imports.
  - Decentralized `slr_cmd.py` into subcommand modules.
  - Introduced `TUIFactory` for UI decoupling.
- **[VERIFIED] Issue #97 (CLI Refactor):** Consolidated command tree and improved UX.
  - Flattened hierarchy: Promoted `rag` to top-level, abolished `list` (merged into `item/collection/system`).
  - Unified `export` polymorphic command (Metadata + Markdown).
  - Unified `slr verify` (Collections + LaTeX).
- **[VERIFIED] Issue #79 (CLI Harmonization):** Standardized positional arguments to named parameters.
  - Refactored `item` and `collection` namespaces for consistency.
  - Migrated to `--key`, `--name`, and `--file` patterns.
  - Updated unit tests to reflect new CLI schema.
- **[VERIFIED] Issue #88 (DBLP Support):** Implemented DBLP Metadata Provider.
  - Created `DBLPAPIClient` for computer science bibliography.
  - Supported search-based and DOI lookups.
  - Integrated into `MetadataAggregatorService` and `GatewayFactory`.
- **[VERIFIED] Issue #87 (INSPIRE-HEP Support):** Implemented INSPIRE-HEP Metadata Provider.
  - Created `InspireHEPAPIClient` for High-Energy Physics literature.
  - Supported DOI, arXiv, and INSPIRE ID lookups.
  - Integrated into `MetadataAggregatorService` and `GatewayFactory`.
- **[VERIFIED] Issue #86 (HAL Support):** Implemented HAL Metadata Provider.
  - Created `HALAPIClient` for the French open-access archive.
  - Supported HAL ID and DOI lookups.
  - Integrated into `MetadataAggregatorService` and `GatewayFactory`.
- **[VERIFIED] Issue #85 (ERIC Support):** Implemented ERIC Metadata Provider.
  - Created `ERICAPIClient` for education research metadata.
  - Supported ERIC Accession Number lookups.
  - Integrated into `MetadataAggregatorService` and `GatewayFactory`.
- **[VERIFIED] Issue #84 (zbMATH Support):** Implemented zbMATH Metadata Provider.
  - Created `zbMATHAPIClient` for mathematical literature indexing.
  - Supported Zbl and DOI lookups.
  - Integrated into `MetadataAggregatorService` and `GatewayFactory`.
- **[VERIFIED] Issue #83 (PubMed Support):** Implemented PubMed Metadata Provider.
  - Created `PubMedAPIClient` using NCBI E-utils (XML parsing).
  - Supported PMID/PMCID lookups with automatic resolution.
  - Integrated into `MetadataAggregatorService` and `GatewayFactory`.
  - Added support for `ncbi_api_key` in configuration.
- **[VERIFIED] Issue #82 (OpenAlex Support):** Implemented full Metadata Provider for OpenAlex.
...

  - Created `OpenAlexAPIClient` with abstract reconstruction logic.
  - Integrated OpenAlex into `MetadataAggregatorService` for transparent enrichment.
  - Refactored `OpenAlexResolver` to leverage the new client architecture.
- **[VERIFIED] Issue #80 (Markdown Export):** Implemented bulk PDF-to-Markdown conversion.
  - Enhanced `AttachmentService` with `bulk_export_markdown` (Parallel).
  - Added `item export-md` and `collection export-md` commands.
  - Integrated `markitdown` for high-fidelity text extraction.
  - Implemented readable filename slugification.
- **[VERIFIED] Issue #92 (Search UX):** Implemented dedicated `search` command.
...

  - Added `SearchCommand` to `cli/commands/search_cmd.py`.
  - Supports keyword, title, and DOI search with Rich table output.
  - **Verification:** 100% functional via live API. Linted and Mypy verified.
- **[VERIFIED] Issue #89 (SLR Audit):** Integrated Citation Guard into SLR Core.
  - Implemented `AuditService.audit_manuscript` in `core/services/audit_service.py`.
  - Added `slr audit` command for recursive LaTeX manuscript verification.
  - **Verification:** Successfully audited test LaTeX files against Zotero + SDB state.
- **[PROTOCOL] GitHub Integration:** Registered `gh` CLI as the mandatory tool for issue reporting.

### Accomplishments (Session: 2026-03-13)

### Phase 24: Systematic Knowledge Retrieval (RAG Core)
- **[VERIFIED] Issue #93 (RAG Core):** Implemented Systematic Knowledge Retrieval for LLMs.
  - Added `RAGService` and `VectorRepository` interfaces to `core/interfaces.py`.
  - Implemented `SQLiteVectorRepository` with Python-native Cosine Similarity (Zero-Dependency).
  - Implemented `OpenAIEmbeddingProvider` and `MockEmbeddingProvider`.
  - Upgraded `AttachmentService` with `get_fulltext` capability using Microsoft's `markitdown`.
  - Integrated full RAG stack into `GatewayFactory` for seamless dependency injection.
  - Added `slr rag ingest`, `slr rag query`, and `slr rag context` commands to the `slr` namespace.
  - **Verification:** 100% Pass Rate on 7 new unit/integration tests. 100% Mypy compliance.

## Current State

*   **Version:** `v2.5.0` (In Development)
*   **Quality:** 100% Pass Rate (455 tests).
*   **Status:** **EVOLVING (RAG Capable)**

## Next Actions (Immediate)
1.  **Operation PDF Resilience:** Finalize Issue #64 (Traceability) feedback in CLI.
2.  **Strategy:** REMIND USER to clone Zotero Desktop source code for "Find Full Text" analysis.
3.  **Infrastructure:** Implement Issue #91 (Cross-Library Item Transfer).
4.  **Integration:** Implement Issue #81 (Direct DOI import).
