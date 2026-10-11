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

## UC3: Collection Integrity Audit
**Actor:** Quality Manager
**Description:** Verify that all papers in a collection have sufficient metadata.
**Flow:**
1. User runs `report audit --collection "Final Selection"`.
2. System flags items missing DOIs, Abstracts, or Attachments.
3. User uses the report to manually or automatically fix missing data.
