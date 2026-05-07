# Use Cases

## UC1: Initialize Environment
**Actor:** Researcher
**Description:** Set up the connection to the Zotero API and local configuration.
**Flow:**
1. User runs `zotero-cli init`.
2. System prompts for API Key, Library ID, and Type.
3. System validates credentials with a test connection.
4. System saves `config.toml`.

## UC2: Batch Ingestion from External Sources
**Actor:** Researcher
**Description:** Populate a Zotero collection with candidate papers for review.
**Flow:**
1. User runs `import arxiv --query "..."`.
2. System fetches metadata and creates items in the target collection.
3. System attempts to find and attach open-access PDFs.

## UC3: Interactive Title/Abstract Screening
**Actor:** Reviewer
**Description:** Rapidly screen papers based on Title and Abstract.
**Flow:**
1. User runs `slr screen --source "Raw" --include "Screened"`.
2. System presents papers one by one in a TUI.
3. User presses [I] to include or [E] to exclude with a reason code.
4. System records the decision in a Zotero Standardized Decision Block (SDB).

## UC4: Generate PRISMA Flowchart
**Actor:** Author
**Description:** Visualize the literature selection process for a publication.
**Flow:**
1. User runs `report prisma --collection "Screened"`.
2. System aggregates all decisions from the collection's history.
3. System outputs Mermaid.js code representing the PRISMA funnel.

## UC5: Knowledge Retrieval (RAG)
**Actor:** Researcher
**Description:** Ask questions about the content of the library using an LLM.
**Flow:**
1. User runs `slr rag ingest --collection "Read"`.
2. System converts PDFs to text, generates embeddings, and stores them.
3. User runs `slr rag query "What are the main findings regarding X?"`.
4. System retrieves relevant context and generates an answer using an LLM.

## UC6: Collection Integrity Audit
**Actor:** Quality Manager
**Description:** Verify that all papers in a collection have sufficient metadata.
**Flow:**
1. User runs `slr audit check --collection "Final Selection"`.
2. System flags items missing DOIs, Abstracts, or Attachments.
3. User uses the report to manually or automatically fix missing data.
