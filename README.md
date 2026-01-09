# zotero-cli

![Build Status](https://github.com/fchicout/zotero-cli/actions/workflows/release.yml/badge.svg)
![Tests](https://github.com/fchicout/zotero-cli/actions/workflows/tests.yml/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-80%25-green)
![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

> **The Researcher's Command Line Interface.**
> Import, manage, and analyze your Zotero library with precision.

**zotero-cli** automates the tedious parts of research: bulk importing from arXiv, syncing metadata across providers (CrossRef, Semantic Scholar), detecting duplicates, and visualizing citation networks.

## 🚀 Quick Start

### Installation
```bash
# Download latest binary (Linux/Windows) from Releases
# OR install via pip (if published)
pip install zotero-cli
```

### Configuration
```bash
export ZOTERO_API_KEY="your_key"
export ZOTERO_TARGET_GROUP="https://zotero.org/groups/123"
```

### First Command
Import the top 10 papers on "LLM Security" from arXiv into a "Reading List" folder:
```bash
zotero-cli import --query "LLM Security" --limit 10 --folder "Reading List"
```

---

## 📚 Documentation

| Resource | Description |
| :--- | :--- |
| **[User Guide](docs/USER_GUIDE.md)** | Detailed command reference (Import, Manage, Analyze). |
| **[Architecture](docs/ARCHITECTURE.md)** | Internal design, data flow diagrams, and C4 models. |

---

## ✨ Key Features

*   **🌐 Universal Import:** ArXiv, BibTeX, RIS, Springer CSV, IEEE CSV.
*   **🧠 Metadata Enrichment:** Automatically fetches abstracts and references from Semantic Scholar & CrossRef.
*   **🔗 Citation Graphs:** Generate visual graphs of how papers in your library cite each other.
*   **🧹 Hygiene:** Audit collections for missing PDFs/DOIs and find duplicates.
*   **🏷️ Tag Ops:** Bulk rename, delete, or add tags.

## Development

```bash
git clone https://github.com/fchicout/zotero-cli.git
cd zotero-cli
pip install -e ".[dev]"
pytest
```

## License
MIT License.
