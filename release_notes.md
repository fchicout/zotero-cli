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

