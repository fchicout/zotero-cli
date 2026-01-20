# User Guide (v2.0.0)

## Table of Contents
1.  [Getting Started](#getting-started)
2.  [Setup & Configuration](#setup--configuration)
3.  [Workflow (Screening & Reporting)](#workflow)
4.  [Ingestion (Import)](#ingestion)
5.  [Management (Collections, Tags, Items)](#management)
6.  [Analysis & System](#analysis)

## Getting Started

The fastest way to get started is using the interactive configuration wizard:
```bash
zotero-cli init
```

## 1. Setup and Configuration

### 1.1 Authentication
The `zotero-cli` requires your Zotero API Key and Library information.

#### Option A: Configuration Wizard (Recommended)
Run the following command and follow the prompts:
```bash
zotero-cli init
```
This generates a `config.toml` file in the standard directory:
- **Linux/macOS:** `~/.config/zotero-cli/config.toml`
- **Windows:** `%APPDATA%\zotero-cli\config.toml`

#### Option B: Environment Variables
For CI/CD or ephemeral sessions, use these variables:
- `ZOTERO_API_KEY`: Your secret API key.
- `ZOTERO_LIBRARY_ID`: The ID of the group or user library.
- `ZOTERO_LIBRARY_TYPE`: Either `group` (default) or `user`.
- `ZOTERO_USER_ID`: Your personal Zotero User ID.
- `ZOTERO_TARGET_GROUP`: Full URL to derive ID.

## Workflow

### 1. Screening
**Interactive (TUI):**
The core feature. Launch the "Tinder-for-Papers" interface.
```bash
zotero-cli review screen --source "raw_arXiv" --include "screened" --exclude "excluded"
```
*   **[I]**: Include
*   **[E]**: Exclude (Select reason code)
*   **[S]**: Skip

**Single Decision (CLI):**
Record a decision directly from the terminal.
```bash
zotero-cli review decide --key "ITEM_KEY" --vote "include"
```

### 2. Reporting (PRISMA)
Generate a PRISMA 2020 statistics report.
```bash
zotero-cli report prisma --collection "screened"
```

---

## Ingestion

### Universal File Import
Supports BibTeX (`.bib`), RIS (`.ris`), and CSV (Springer/IEEE).
```bash
zotero-cli import file papers.bib --collection "Imported"
```

### Online Query (arXiv)
Import directly from arXiv using a query.
```bash
zotero-cli import arxiv --query "LLM AND Security" --limit 50 --collection "AI Security"
```

---

## Management

### Collections
```bash
zotero-cli collection list
zotero-cli collection clean --collection "Trash"
```

### Tags
```bash
zotero-cli tag list
zotero-cli tag purge --tag "junk"
```

### Items
```bash
zotero-cli item list --collection "MyCol"
zotero-cli item inspect BQPLL87F
zotero-cli item move --item-id "KEY" --target "Read"
```

---

## Analysis & System

### System Info
Check your configuration and connection status.
```bash
zotero-cli system info
```

### Audit
Check for missing metadata (Abstracts, DOIs, PDFs).
```bash
zotero-cli analyze audit --collection "Critical Review"
```