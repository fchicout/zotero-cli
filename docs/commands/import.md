# Command: `import`

Ingest research papers from various external sources and local files.

## Verbs

### `file`
Import items from local files. Supports `.bib` (BibTeX), `.ris` (RIS), and `.csv` (IEEE Xplore or Springer formats).

**Usage:**
```bash
zotero-cli import file "references.bib" --collection "MySearch"
```

**Parameters:**
*   `file`: (Positional, Required) Path to the file.
*   `--collection`: (Required) Target collection name or key.
*   `--verbose`: Show detailed import logs.

---

### `arxiv`
Import papers directly from ArXiv using IDs or search queries.

**Usage:**
```bash
zotero-cli import arxiv --query "AI Security" --collection "ArXiv Imports"
```

**Parameters:**
*   `--query`: ArXiv search query.
*   `--file`: Optional path to a file containing the query.
*   `--collection`: (Required) Target collection name or key.
*   `--limit`: Maximum items to import (default: 100).

---

### `manual`
Add a paper manually by providing its core metadata.

**Usage:**
```bash
zotero-cli import manual --title "Paper Title" --arxiv-id "2401.xxx" --abstract "..." --collection "Inbox"
```