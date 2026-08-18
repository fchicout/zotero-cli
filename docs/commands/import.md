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

---

### `bdtd`
Import thesis/dissertation metadata from Brazilian BDTD into a Zotero collection. Accepts a single BDTD record ID, institutional repository handle URL, or DOI, or a free-text `--query` to bulk-import multiple matching theses/dissertations.

**Usage:**
```bash
zotero-cli import bdtd "https://repositorio.ufpe.br/handle/123456789/51746" --collection "BR_THESES"
zotero-cli import bdtd --query "aprendizado de maquina" --collection "Brazilian_ML" --limit 20
```

**Parameters:**
*   `identifier`: (Positional) BDTD record ID, repository handle URL, or DOI. Required unless `--query` is given.
*   `--query`: Free-text search query for bulk import. Required unless `identifier` is given.
*   `--limit`: Max results to import for `--query`. Default: `20`.
*   `--collection`: (Required) Target collection name or key.
*   `--verbose`: Show detailed import logs.

> *Note: `--query` bulk imports skip PDF resolution (too slow to scrape per record) — run `item pdf fetch` afterward to attach PDFs.*