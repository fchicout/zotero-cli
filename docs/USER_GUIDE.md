# User Guide

## Table of Contents
1.  [Getting Started](#getting-started)
2.  [Importing Papers](#importing-papers)
3.  [Managing Collections](#managing-collections)
4.  [Analyzing Your Library](#analyzing-your-library)
5.  [Advanced Search](#advanced-search)
6.  [Troubleshooting](#troubleshooting)

## Getting Started

Ensure you have your environment variables set:
```bash
export ZOTERO_API_KEY="key"
export ZOTERO_TARGET_GROUP="https://zotero.org/groups/123"
```

## Importing Papers

### From arXiv
**Single Paper:**
Add a specific paper by ID.
```bash
zotero-cli add --arxiv-id "2301.00001" --title "Paper Title" --abstract "Abstract..." --folder "My List"
```

**Bulk Search:**
Search arXiv and import results.
```bash
zotero-cli import --query "LLM cybersecurity" --limit 50 --folder "AI Security"
```

### From Files
**BibTeX:**
```bash
zotero-cli bibtex --file refs.bib --folder "Imported"
```

**RIS:**
```bash
zotero-cli ris --file citations.ris --folder "Imported"
```

**CSV (Springer/IEEE):**
```bash
zotero-cli springer-csv --file springer.csv --folder "Springer"
zotero-cli ieee-csv --file ieee.csv --folder "IEEE"
```

## Managing Collections

### Listing
View all collections in your library with their item counts.
```bash
zotero-cli list-collections
```

### Attachments
**Auto-Attach PDFs:**
Find missing PDFs via Unpaywall/CrossRef and upload them.
```bash
zotero-cli attach-pdf --collection "Reading List"
```

**Remove Attachments:**
Delete all child items (PDFs/Snapshots) to save storage space.
```bash
zotero-cli remove-attachments --folder "Old Papers"
```

### Organization
**Move Item:**
Transfer an item from one collection to another using its DOI or arXiv ID.
```bash
zotero-cli move --id "10.1234/doi" --from-col "Inbox" --to-col "Read"
```

**Empty Collection:**
⚠️ **Destructive:** Removes all items from a collection.
```bash
zotero-cli empty-collection --collection "Trash"
```

### Tag Management
**List Tags:**
```bash
zotero-cli tag list
```

**Rename Tag:**
Bulk rename a tag across the entire library.
```bash
zotero-cli tag rename --old "ai" --new "artificial-intelligence"
```

**Delete Tag:**
Remove a tag from all items.
```bash
zotero-cli tag delete --tag "junk"
```

**Add/Remove on Item:**
Modify tags for a specific Zotero Item Key.
```bash
zotero-cli tag add --item "ITEMKEY123" --tags "important,review"
zotero-cli tag remove --item "ITEMKEY123" --tags "todo"
```

## Analyzing Your Library

### Duplicates
Find items with the same Title or DOI across multiple collections.
```bash
zotero-cli duplicates --collections "Inbox, Archive"
```

### Citation Graph
Generate a Graphviz DOT file showing citation relationships between papers.
```bash
zotero-cli graph --collections "AI Security" > graph.dot
# Convert to PNG (requires Graphviz installed)
dot -Tpng graph.dot -o graph.png
```

### Audit
Check for missing metadata (Abstracts, DOIs, PDFs) in a collection.
```bash
zotero-cli audit --collection "Critical Review"
```

## Advanced Search (arXiv DSL)

The `search-arxiv` command supports a structured query language for precise filtering.

**Syntax:** `key: value; key2: value2`

**Supported Keys:**
*   `terms`: The search query (supports `AND`, `OR`, `field=value`).
*   `date_range`: e.g., `from 2023-01-01`.
*   `size`: Max results (default 100).
*   `order`: `announced_date_first` (ascending) or `-announced_date_first` (descending).
*   `classification`: e.g., `Computer Science (cs)`.

**Example:**
```bash
zotero-cli search-arxiv --query "terms: title=LLM; date_range: from 2023-01-01; size: 20"
```