# Specification: RAG Verification v1.1

**Status:** DRAFT
**Related Issues:** #112
**Author:** Hamilton (The Council) / Argentis (Lifecycle)

## 1. Objective
To introduce a formal **Verification Layer** into the RAG workflow. This ensures that any information retrieved and presented to the user (or fed into an LLM) is grounded in **verified** and **screened** academic sources, adhering to the `protocol:citation_guard`.

## 2. The Verification Contract

### 2.1 Verification Criteria
A RAG Search Result is considered **Verified** if it meets the following hierarchical criteria:
1.  **Identifier Presence:** The source item MUST have a valid DOI or arXiv ID.
2.  **Internal Integrity:** The source item MUST pass the `IntegrityService` basic audit (Title and Abstract present).
3.  **Approval Status:** The source item MUST be tagged with `rsl:include` or have an "accepted" screening decision in its notes.

### 2.2 Formal Interface
The `RAGService` will be extended with:
- **`verify_results(results: List[SearchResult]) -> List[VerifiedSearchResult]`**

```python
@dataclass
class VerifiedSearchResult(SearchResult):
    is_verified: bool = False
    verification_errors: List[str] = field(default_factory=list)
    screening_status: str = "unknown" # accepted, rejected, pending
    citation_key: Optional[str] = None # For easy inclusion in manuscripts
```

## 3. Workflow Integration

### 3.1 CLI: `rag query --verify`
When the `--verify` flag is provided:
1.  The system performs semantic search as usual.
2.  Each result is passed through the `VerificationLayer`.
3.  In human-readable output, verified results are marked with a green check (✅) and unverified ones with a red cross (❌) plus a reason.
4.  The output SHOULD include the `citation_key` for verified items to support LaTeX/Markdown writing.
5.  In JSON output, the `is_verified`, `verification_errors`, and `citation_key` fields are populated.

### 3.2 Safety & Integrity (Mandatory)
- **Vector Database Safety:** During any testing or implementation that modifies the vector store, the current `vector_store.sqlite` MUST be backed up.
- **Snippet High-Fidelity:** The untruncated snippet MUST be preserved in `--json` output to allow human verification of the citation context.

### 3.3 Cognitive Safeguards
- **VETO: Unverified Citation:** If a result fails verification, it should be clearly flagged to prevent "hallucinated authority."
- **Traceability:** Every verification failure must link back to the specific missing metadata (e.g., "Missing DOI").

## 4. Implementation Plan
1.  **Phase 1: Domain Update**
    - [ ] Update `RAGService` interface in `interfaces.py`.
    - [ ] Update `SearchResult` model in `models.py` (or create `VerifiedSearchResult`).
2.  **Phase 2: Service Implementation**
    - [ ] Implement `verify_results` in `rag_service.py` leveraging `IntegrityService`.
3.  **Phase 3: CLI Integration**
    - [ ] Add `--verify` flag to `rag query`.
    - [ ] Update UI table to display verification status and citation key.
