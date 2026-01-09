# User Guide

## Table of Contents
1.  [Getting Started](#getting-started)
2.  [Importing Papers](#importing-papers)
3.  [Managing Collections](#managing-collections)
4.  [Analyzing Your Library](#analyzing-your-library)
5.  [Troubleshooting](#troubleshooting)

## Getting Started

Ensure you have your environment variables set:
```bash
export ZOTERO_API_KEY="key"
export ZOTERO_TARGET_GROUP="https://zotero.org/groups/123"
```

## Importing Papers

### From arXiv
**Single Paper:**
```bash
zotero-cli add --arxiv-id "2301.00001" --title "Paper Title" --abstract "Abstract..." --folder "My List"
```

**Bulk Search:**
```bash
# By query
zotero-cli import --query "LLM cybersecurity" --limit 50 --folder "AI Security"

# By complex query
zotero-cli search-arxiv --query "terms: title=LLM; date_range: from 2023-01-01"
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

### Attachments
Remove PDFs to save space:
```bash
zotero-cli remove-attachments --folder "Old Papers"
```

Auto-attach PDFs (via Unpaywall):
```bash
zotero-cli attach-pdf --collection "Reading List"
```

### Organization
**Move Item:**
```bash
zotero-cli move --id "10.1234/doi" --from-col "Inbox" --to-col "Read"
```

**Tags:**
```bash
zotero-cli tag list
zotero-cli tag rename --old "ai" --new "artificial-intelligence"
zotero-cli tag delete --tag "junk"
```

## Analyzing Your Library

### Duplicates
Find items with same Title or DOI across collections:
```bash
zotero-cli duplicates --collections "Inbox, Archive"
```

### Citation Graph
Generate a Graphviz DOT file showing citation links:
```bash
zotero-cli graph --collections "AI Security" > graph.dot
# Convert to PNG (requires Graphviz installed)
dot -Tpng graph.dot -o graph.png
```

### Audit
Check for missing metadata (Abstracts, DOIs, PDFs):
```bash
zotero-cli audit --collection "Critical Review"
```
