# 📥 DEV_INBOX: RAG Verification (Issue #112 / Spec v1.1)

**Status:** 🟢 READY FOR IMPLEMENTATION
**Project:** zotero-cli
**Spec:** [docs/specs/RAG_VERIFICATION_v1.1.md](../docs/specs/RAG_VERIFICATION_v1.1.md)
**Priority:** High

## 🛠️ Task Description
Implement the **Verification Layer** for RAG search results to ensure academic integrity and provide citation-ready metadata to researchers.

## 📋 Technical Requirements
1.  **Phase 1: Domain Update**
    - Add `VerifiedSearchResult` to `src/zotero_cli/core/models.py`.
    - Extend `RAGService` interface in `src/zotero_cli/core/interfaces.py`.
2.  **Phase 2: Service Logic**
    - Implement `verify_results` in `src/zotero_cli/core/services/rag_service.py`.
    - Integrate with `IntegrityService` for metadata checks.
3.  **Phase 3: CLI Integration**
    - Add `--verify` flag to `rag query` command.
    - Update human-readable table and JSON output.

## 🛑 Critical Vetoes
- **No data loss:** Ensure `vector_store.sqlite` is protected (Backup created).
- **No truncation:** Snipet in JSON output MUST be the full text.

---
**Lead Persona:** Hamilton (Lead Engineer)
**Protocol:** Valerius Protocol (Verify-Expand-Verify)
