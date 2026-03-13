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

## Accomplishments (Session: 2026-03-13)

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
