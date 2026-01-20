<!-- BADGES_START -->
![Version](https://img.shields.io/badge/version-2.0.0-blue) ![Coverage](https://img.shields.io/badge/coverage-79%25-yellow) ![Lint](https://img.shields.io/badge/ruff-passing-brightgreen) ![Types](https://img.shields.io/badge/mypy-passing-brightgreen) ![License](https://img.shields.io/badge/license-MIT-lightgrey) ![Python](https://img.shields.io/badge/python-3.10+-blue)
<!-- BADGES_END -->

# zotero-cli

![Build Status](https://github.com/fchicout/zotero-cli/actions/workflows/release.yml/badge.svg)
![Tests](https://github.com/fchicout/zotero-cli/actions/workflows/tests.yml/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-81%25-green)
![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Semantic Version](https://img.shields.io/badge/semver-2.0.0-orange)

> **The Researcher's Command Line Interface.**
> Rigorous Systematic Literature Reviews (SLR), made scriptable.

**zotero-cli** transforms Zotero from a reference manager into a **Systematic Review Engine**. It follows the **Noun-Verb** pattern for a clean, predictable automation experience.

## 🌟 The SLR Workflow (v2.0)

We support the rigorous **Kitchenham/Wohlin** review protocol.

```mermaid
graph LR
    A[Raw Source] -->|import| B(Collection: Raw)
    B -->|review screen| C{Screening}
    C -->|review decide| D(Collection: Screened)
    C -->|review decide| E(Collection: Excluded)
    D -->|report snapshot| F[Audit Snapshot]
    D -->|report prisma| G[PRISMA Flow]
    D -->|analyze lookup| H[Synthesis Table]
```

## 📚 Command Reference

Detailed documentation is available for each command noun:

| Noun | Description | Key Verbs |
| :--- | :--- | :--- |
| **[`init`](docs/commands/init.md)** | Configuration | `(default)` |
| **[`review`](docs/commands/review.md)** | SLR Workflow | `screen`, `decide`, `audit`, `prune`, `migrate` |
| **[`item`](docs/commands/item.md)** | Paper/Item Ops | `inspect`, `move`, `update`, `delete`, `pdf` |
| **[`collection`](docs/commands/collection.md)** | Folder Ops | `list`, `create`, `rename`, `delete`, `backup` |
| **[`import`](docs/commands/import.md)** | Ingest | `arxiv`, `file (IEEE/Springer/Canonical)` |
| **[`report`](docs/commands/report.md)** | Output | `prisma`, `snapshot`, `screening`, `status` |
| **[`analyze`](docs/commands/analyze.md)** | Analytics | `audit`, `lookup`, `graph`, `shift` |
| **[`tag`](docs/commands/tag.md)** | Taxonomy | `list`, `add`, `remove`, `purge` |
| **[`list`](docs/commands/list.md)** | Generic List | `items`, `collections`, `groups` |
| **[`storage`](docs/commands/storage.md)** | Maintenance | `checkout` |
| **[`serve`](docs/commands/serve.md)** | Integration | `(default)` |
| **[`system`](docs/commands/system.md)** | Maintenance | `backup`, `restore`, `normalize`, `info` |

## 🚀 Key v2.0 Features

*   **Standardized CSV:** A unified canonical format for importing from IEEE, Springer, and BibTeX.
*   **System Portability:** Full library or scoped collection backup to `.zaf` (LZMA compressed).
*   **Drift Detection:** `analyze shift` detects if items have moved between snapshots.
*   **Set Integrity:** `review prune` ensures your Included and Excluded sets are disjoint.
*   **Audit Dashboard:** `report status` provides a Rich TUI dashboard of your screening progress.

---

## Quick Start

### 1. Install
```bash
pip install zotero-cli
```

### 2. Configure
```bash
zotero-cli system info  # Check if config is found
```

## Development & Contribution

We follow strict **SOLID** principles, 100% Mypy compliance, and mandatory E2E verification.

```bash
git clone https://github.com/fchicout/zotero-cli.git
cd zotero-cli
pip install -e ".[dev]"
pytest --cov=src
```

## License
MIT License. See [LICENSE](LICENSE) for details.