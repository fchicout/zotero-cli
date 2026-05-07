# Functional Requirements

## 1. System Initialization
- **REQ-1.1:** The system MUST provide an interactive configuration wizard (`init`) to set up Zotero API credentials.
- **REQ-1.2:** The system MUST support authentication via configuration files and environment variables (`ZOTERO_API_KEY`, `ZOTERO_LIBRARY_ID`).

## 2. Bibliographic Ingestion
- **REQ-2.1:** The system MUST import papers from the arXiv API based on keyword queries.
- **REQ-2.2:** The system MUST import papers from local files in BibTeX, RIS, and CSV (Springer/IEEE) formats.
- **REQ-2.3:** The system MUST support direct item creation via DOI resolution.
- **REQ-2.4:** The system MUST allow manual item creation with mandatory fields like Title and Collection.

## 3. Library Management
- **REQ-3.1:** The system MUST list, create, and clean Zotero collections.
- **REQ-3.2:** The system MUST list, inspect, move, and add items within collections.
- **REQ-3.3:** The system MUST provide tag management capabilities, including listing and purging unused tags.

## 4. Systematic Literature Review (SLR) Workflow
- **REQ-4.1:** The system MUST provide an interactive Terminal User Interface (TUI) for rapid Title/Abstract screening.
- **REQ-4.2:** The system MUST support "Standardized Decision Blocks" (SDB) saved as Zotero child notes for auditability.
- **REQ-4.3:** The system MUST record screening decisions including include/exclude status, reason codes, and timestamps.
- **REQ-4.4:** The system MUST support multi-phase screening (e.g., Title/Abstract vs. Full-Text).

## 5. Reporting and Audit
- **REQ-5.1:** The system MUST generate PRISMA 2020 flowcharts in Mermaid.js format based on screening decisions.
- **REQ-5.2:** The system MUST audit collections for missing metadata (Abstracts, DOIs, PDFs).
- **REQ-5.3:** The system MUST generate immutable JSON snapshots of collections for reproducibility.

## 6. Advanced Knowledge Retrieval (RAG)
- **REQ-6.1:** The system MUST extract full text from PDF attachments using markdown conversion.
- **REQ-6.2:** The system MUST support ingesting document embeddings into a local vector repository.
- **REQ-6.3:** The system MUST provide a RAG interface to query the library using Large Language Models (LLMs).

# Non-Functional Requirements

- **REQ-NF-1 (Security):** API keys MUST NEVER be logged or displayed in plain text during normal operation.
- **REQ-NF-2 (Usability):** The screening TUI MUST support keyboard shortcuts for high-velocity operation.
- **REQ-NF-3 (Portability):** The system MUST run on Linux, macOS, and Windows with Python 3.10+.
- **REQ-NF-4 (Performance):** Bulk operations (like PDF-to-Markdown export) SHOULD support parallel processing.
