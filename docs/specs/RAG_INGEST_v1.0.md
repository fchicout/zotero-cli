# RAG Ingest Specification v1.0

**Status:** 🟡 DRAFT
**Architect:** Hamilton (Council)
**Validator:** Smithy / TypeSpec
**Date:** 2026-04-22

## 1. Executive Summary
This specification outlines the refactoring of the RAG Ingest functionality to align with SOLID principles, optimize performance via pre-filtering, and ensure zero-persistence of sensitive data during extraction.

## 2. Technical Requirements

### [SPEC-RAG-001] Predicate-Driven Selection Strategy
- **Logic:** Decouple "Selection" (finding items) from "Ingestion" (processing text).
- **Protocol:** Offload `rsl:include` tag filtering to the `ZoteroGateway.search_items` (API-side).
- **Handoff:** The `ingest` method receives a pre-validated `List[ItemKey]`.

### [SPEC-RAG-002] High-Fidelity QA Score Extraction
- **Path:** `parsed_json["data"]["quality_assessment"]["total"]`.
- **Fidelity:** Use the raw numeric value. No normalization or mapping to 0.0-1.0 scale.
- **Robustness:** Default to `0.0` if path is missing.

### [SPEC-RAG-003] Formal Interface & Strategy Decoupling (SOLID)
- **DIP:** Inject `FullTextProvider` and `TextSplitter` interfaces.
- **Strategy:** Move character-based splitting to `FixedSizeChunker : TextSplitter`.

### [SPEC-RAG-004] Atomic Progress & Count Integrity
- **UX:** Initialize progress bar with `total=len(keys)`.
- **Fidelity:** Increment progress for every item in the dispatch list, marking failures as "Skipped".

### [SPEC-RAG-005] Zero-Persistence Attachment Lifecycle
- **Safety:** Use `tempfile.TemporaryDirectory` for PDF handling.
- **Veto:** Permanent files or intermediate `.md` files are strictly forbidden.

## 3. Implementation Plan
1. **Refactor Core Interfaces** (`src/zotero_cli/core/interfaces.py`).
2. **Update RAGServiceBase** with Selection logic.
3. **Correct SDB Path** in `_get_item_max_qa_score`.
4. **Implement Context-Aware Progress** in `rag_cmd.py`.
