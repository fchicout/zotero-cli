# 📥 QUALITY_INBOX: RAG Verification (Spec v1.1)

**Status:** 🟡 WAITING FOR DEV
**Related Task:** RAG Verification (DEV_INBOX)

## ✅ Verification Criteria
- [ ] **Unit Tests:** `RAGService.verify_results` must correctly flag items missing DOI/arXiv ID.
- [ ] **Integration Tests:** `rag query --verify --json` must return `is_verified: true` for approved items.
- [ ] **Fidelity Test:** Verify that snippet length in JSON matches source text length (no truncation).
- [ ] **Workflow Test:** Verify `citation_key` is present in the output.

## ⚠️ Safety Gate
- [ ] Verify that research database (`vector_store.sqlite.bak_research`) is restorable and unharmed after test suite execution.
