# User Guide (v1.0.0)

## Table of Contents
1.  [Getting Started](#getting-started)
2.  [Workflow (Screening & Reporting)](#workflow)
3.  [Ingestion (Import)](#ingestion)
4.  [Management (Tags, PDFs, Cleaning)](#management)
5.  [Analysis & Discovery](#analysis)

## Getting Started

Ensure you have your environment variables set:
```bash
export ZOTERO_API_KEY="key"
export ZOTERO_USER_ID="123456"
# Optional: Set a default group URL to skip finding it
export ZOTERO_TARGET_GROUP="https://zotero.org/groups/123"
```

---

## Workflow

### 1. Screening (TUI)
The core feature. Launch the "Tinder-for-Papers" interface.
```bash
zotero-cli screen --source "raw_arXiv" --include "screened" --exclude "excluded"
```
*   **[I]**: Include
*   **[E]**: Exclude (Select reason code)
*   **[S]**: Skip

### 2. Reporting (PRISMA)
Generate a PRISMA 2020 statistics report and flowchart.
```bash
zotero-cli report prisma --collection "screened" --output-chart "prisma.png"
```

### 3. Snapshotting
Create an immutable JSON audit trail of your review state.
```bash
zotero-cli report snapshot --collection "screened" --output "audit_trail.json"
```

---

## Ingestion

### Universal File Import
Supports BibTeX (`.bib`), RIS (`.ris`), and CSV (Springer/IEEE).
```bash
zotero-cli import file papers.bib --collection "Imported"
zotero-cli import file ieee_export.csv --collection "IEEE"
```

### Online Query (arXiv)
Import directly from arXiv using a query.
```bash
zotero-cli import arxiv --query "LLM AND Security" --limit 50 --collection "AI Security"
```

### Manual Entry
Add a single paper.
```bash
zotero-cli import manual --arxiv-id "2301.00001" --title "Paper Title" --abstract "Abstract..." --collection "My List"
```

---

## Management

### Tags
```bash
zotero-cli manage tags list
zotero-cli manage tags rename --old "ai" --new "artificial-intelligence"
zotero-cli manage tags delete --tag "junk"
zotero-cli manage tags add --item "KEY123" --tags "review,prio"
```

### PDFs
**Fetch:** Find missing PDFs via Unpaywall.
```bash
zotero-cli manage pdfs fetch --collection "Reading List"
```
**Strip:** Remove all attachments to save space.
```bash
zotero-cli manage pdfs strip --collection "Old Papers"
```

### Hygiene
**Duplicates:** Find duplicate titles/DOIs.
```bash
zotero-cli manage duplicates --collections "Inbox, Archive"
```
**Move:** Transfer an item.
```bash
zotero-cli manage move --item-id "10.1234/doi" --source "Inbox" --target "Read"
```
**Clean:** Empty a collection (Destructive!).
```bash
zotero-cli manage clean --collection "Trash"
```
**Migrate:** Upgrade audit notes to Standardized Decision Block (SDB) v1.1.
```bash
zotero-cli manage migrate --collection "raw_arXiv"
```

---

## Analysis

### Discovery
```bash
zotero-cli list collections   # See what you have
zotero-cli list groups        # Find your Group IDs
zotero-cli list items --collection "MyCol"
```

### Audit
Check for missing metadata (Abstracts, DOIs, PDFs).
```bash
zotero-cli analyze audit --collection "Critical Review"
```

### Lookup
Bulk fetch metadata for a list of Item Keys (useful for synthesis tables).
```bash
zotero-cli analyze lookup --keys "K1,K2,K3" --format table
```

### Graph
Generate a Graphviz DOT file of citation networks.
```bash
zotero-cli analyze graph --collections "AI Security" > graph.dot
```

### Find (Read-Only)
Search arXiv without importing.
```bash
zotero-cli find arxiv --query "terms: title=LLM; size: 10"
```
