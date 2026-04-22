# zotero-cli: Release Roadmap
**Status:** SOVEREIGN (Managed by The Council)
**Source of Truth:** GitHub Issues

## Active Release: v2.6.0 (The Refactoring & Infrastructure Cycle)

### Primary Objectives
- [ ] **Architecture:** Decompose SLR Core and refactor God Objects (Issue #96).
- [ ] **Infrastructure:** Complete Metadata Provider suite (OpenAlex, PubMed, DBLP, etc. - Issues #82-#88).
- [ ] **UX:** Implement bulk PDF-to-Markdown conversion via `markitdown` (Issue #80).
- [x] **UX:** Implement dedicated `search` command in CLI (Issue #92).
- [x] **Methodology:** Integrate Citation Guard as `slr audit` (Issue #89).
- [x] **Integration:** Implement direct DOI import (Issue #81).
- [x] **Quality:** Implement RAG Verification Engine (Spec v1.1) and Fidelity Guards.

### Mandatory Release Gate
- [x] **Cortex Code Review Protocol (ADR-004):** Final audit for SOLID/DRY/KISS compliance after refactoring.

## Completed Milestones
- **v2.5.0:** Systematic Knowledge Retrieval (RAG Core), BibTeX Export, and Universal Item Transfer.
- **v2.4.0:** Maintenance & Optimization (Reset Engine, Granular Purging).
- **v2.3.0:** Data Extraction Phase (TUI + Schema Validator + Export).
- **v2.2.0:** Semantic CLI Consolidation (the `slr` namespace).
- **v2.1.0:** Storage Offloading and Local API Support.
- **v2.0.0:** Major Architectural Shift (Service-Oriented Logic).

---
**Protocol:** Update this file only after GitHub Issue triage or during Release Synthesis.
