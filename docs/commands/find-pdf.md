# Command: `find-pdf`

Resilient PDF Discovery Engine (Operation PDF Resilience).
This command manages the retrieval of PDFs for Zotero items using multiple strategies (Unpaywall, OpenAlex, ArXiv, Semantic Scholar, Generic Scrapers).

It uses a persistent Job Queue (SQLite) to ensure reliability, traceability, and state recovery.

## Usage

### Basic Usage
Find PDFs for specific items:
```bash
zotero-cli find-pdf ITEMKEY1 ITEMKEY2
```

### Process a Collection
Find PDFs for all items in a collection that are missing attachments:
```bash
zotero-cli find-pdf --collection "My Collection"
```

### Async Mode
Enqueue jobs but do not start the worker immediately (useful for batch queuing):
```bash
zotero-cli find-pdf --collection "My Collection" --async
```

### Watch Mode
Monitor the progress of active jobs in a live dashboard:
```bash
zotero-cli find-pdf --watch
```

### Resume
Resume processing of pending jobs (e.g., after a crash or network interruption):
```bash
zotero-cli find-pdf --resume
```
