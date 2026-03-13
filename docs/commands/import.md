# Command: `import`

Ingest research papers from various external sources and local files.

## Verbs

### `file`
Import papers from a local file. Supports `.bib`, `.ris`, and `.csv` (IEEE, Springer, and Zotero-CLI Canonical).

**Usage:**
```bash
zotero-cli import file "citations.bib" --collection "New Collection"
```

**Supported CSV Formats:**
1.  **IEEE Xplore**: Auto-detected by 'Document Title' header.
2.  **Springer Link**: Auto-detected by 'Item Title' header.
3.  **Canonical**: Auto-detected by 'title' and 'doi' headers (lowercase).


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

### `doi`
Import a single paper directly using its DOI (Digital Object Identifier). The tool automatically enriches metadata from available providers (Semantic Scholar, CrossRef, Unpaywall).

**Usage:**
```bash
zotero-cli import doi "10.1038/s41586-023-06222-4" --collection "DOI Imports"
```

**Parameters:**
*   `doi`: (Positional, Required) The DOI string.
*   `--collection`: (Required) Target collection name or key.
*   `--verbose`: Show enrichment details during import.

---

### `manual`
Add a paper manually by providing its core metadata.

**Usage:**
```bash
zotero-cli import manual --title "Paper Title" --arxiv-id "2401.xxx" --abstract "..." --collection "Inbox"
```