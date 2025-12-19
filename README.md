# Academic Reference Toolkit

![Build Status](https://github.com/fchicout/academic-ref-toolkit/actions/workflows/release.yml/badge.svg)
![Tests](https://github.com/fchicout/academic-ref-toolkit/actions/workflows/tests.yml/badge.svg)
![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

> **Fork Notice:** This repository extends the original [paper2zotero](https://github.com/ORIGINAL_AUTHOR/paper2zotero) project with additional utilities for academic reference management.

## About This Fork

This fork adds custom utilities to the original paper2zotero tool:

**Original Project (paper2zotero):**
- Zotero integration for importing papers from arXiv, BibTeX, RIS, and CSV
- Created by [ORIGINAL_AUTHOR_NAME]
- Located in `src/paper2zotero/`

**My Contributions (`bibtools/` folder):**
- **CSV to BibTeX Converter** - Fix concatenated author names in Springer exports
- **Article Extractor** - Extract DOI, Title, and Abstract for systematic review screening
- **Zotero DOI Updater** - Fix missing DOIs in your Zotero library
- **Zotero Item Reclassifier** - Correct item types (e.g., preprint → journal article)

These utilities were built to solve real-world problems I encountered during my research workflow.

## Project Structure

```
academic-ref-toolkit/
├── src/paper2zotero/       # Original project (upstream)
│   ├── cli/
│   ├── core/
│   └── infra/
├── tests/                  # Tests for paper2zotero
│
└── bibtools/               # MY WORK - All my utilities
    ├── core/               # Business logic
    │   ├── csv_converter.py             # CSV to BibTeX conversion
    │   ├── author_fixer.py              # Author name fixing
    │   ├── article_extractor.py         # Article extraction
    │   ├── zotero_doi_updater.py        # DOI updater
    │   └── zotero_item_reclassifier.py  # Item type fixer
    ├── cli/                # Command-line interfaces
    ├── web/                # Web interface (Flask)
    ├── utils/              # File handling utilities
    ├── tests/              # My tests
    ├── data/               # My data folders
    ├── docs/               # My documentation
    ├── pyproject.toml      # My package config
    └── README.md           # My utilities README
```

```
academic-ref-toolkit/
├── src/paper2zotero/       # Main Zotero integration tool
│   ├── cli/               # Command-line interface
│   ├── core/              # Core models and interfaces
│   └── infra/             # arXiv, BibTeX, RIS, CSV libraries
├── tests/                  # Tests for paper2zotero
│
├── custom/                 # Optional utilities (standalone)
│   ├── core/              # Business logic
│   │   ├── csv_converter.py          # CSV to BibTeX conversion
│   │   ├── author_fixer.py           # Author name fixing
│   │   ├── article_extractor.py      # Article extraction
│   │   ├── zotero_doi_updater.py     # DOI updater
│   │   └── zotero_item_reclassifier.py # Item type fixer
│   ├── cli/               # Command-line interfaces
│   ├── web/               # Web interface (Flask)
│   └── utils/             # File handling utilities
├── tests_custom/          # Tests for custom utilities
│
└── data/
    ├── input/            # Place your CSV files here
    └── output/           # Generated BibTeX files
```

---

## Original paper2zotero Features

For documentation on the original paper2zotero tool, see below. For my custom utilities, jump to [Custom Utilities](#custom-utilities).

**Features:**
*   **arXiv Integration**: Search and bulk import papers directly from arXiv queries
*   **BibTeX & RIS Support**: Import bibliographic data from standard file formats
*   **CSV Support**: Import from Springer and IEEE CSV exports
*   **Zotero Management**: Automatically creates collections (folders) if they don't exist
*   **Maintenance**: Utility to remove attachments (PDFs/snapshots) to save storage space
*   **Flexible Input**: Accepts queries via command arguments, files, or standard input (pipes)

## Installation

### From Binaries (Recommended)
Download the latest release for your platform from the [Releases Page](https://github.com/fchicout/paper2zotero/releases).

*   **Linux**: Download `.deb` (Debian/Ubuntu) or `.rpm` (Fedora/RHEL).
    ```bash
    # Ubuntu/Debian
    sudo dpkg -i paper2zotero-linux-amd64.deb
    
    # Fedora/RHEL
    sudo rpm -i paper2zotero-linux-amd64.rpm
    ```
*   **Windows**: Download `paper2zotero.exe` and add it to your PATH.
*   **Standalone**: Download the binary `paper2zotero` and run it directly.

### From Source
Requires Python 3.8+.

```bash
git clone https://github.com/fchicout/paper2zotero.git
cd paper2zotero
pip install .
```

## Configuration

You must set the following environment variables to authenticate with Zotero:

```bash
export ZOTERO_API_KEY="your_api_key_here"
export ZOTERO_TARGET_GROUP="https://www.zotero.org/groups/1234567/group_name"
```
*   **ZOTERO_API_KEY**: Create one at [Zotero API Settings](https://www.zotero.org/settings/keys).
*   **ZOTERO_TARGET_GROUP**: The URL or ID of the group library you want to manage.

## Usage

### 1. Add a Single Paper (arXiv)
Add a specific paper by its arXiv ID.

```bash
paper2zotero add --arxiv-id "2301.00001" \
                 --title "Sample Paper Title" \
                 --abstract "This is the abstract..." \
                 --folder "My Reading List"
```

### 2. Bulk Import from arXiv
Search arXiv and import all matching results.

**Direct Query:**
```bash
paper2zotero import --query "LLM cybersecurity" --limit 50 --folder "AI Security" --verbose
```

**From File:**
```bash
paper2zotero import --file query.txt --folder "AI Security"
```

**From Pipe:**
```bash
echo "generative AI" | paper2zotero import --folder "GenAI" --limit 10
```

### 3. Import from BibTeX
Import references from a `.bib` file (e.g., exported from Google Scholar, ScienceDirect).

```bash
paper2zotero bibtex --file references.bib --folder "Literature Review" --verbose
```

### 4. Import from RIS
Import references from a `.ris` file.

```bash
paper2zotero ris --file citations.ris --folder "Research 2025"
```

### 5. Import from Springer CSV
Import references from a Springer Search Results CSV export.

```bash
paper2zotero springer-csv --file SearchResults.csv --folder "Springer Papers"
```

### 6. Import from IEEE CSV
Import references from an IEEE Xplore CSV export.

```bash
paper2zotero ieee-csv --file export2025.csv --folder "IEEE Papers"
```

### 7. Remove Attachments
Remove all child items (PDFs, snapshots) from items in a specific folder to clean up storage.

```bash
paper2zotero remove-attachments --folder "AI Security" --verbose
```

## Development

```bash
# Install dev dependencies
pip install -e .

# Run tests
python -m unittest discover tests
```

---

## Custom Utilities (bibtools)

**This is my work** - The `bibtools/` folder contains standalone tools I built for advanced workflows. These are independent from the original paper2zotero code and can be used separately.

**Documentation:** 
- [Quick Start (5 min)](bibtools/docs/QUICK_START.md) - Get started quickly
- [User Guide](bibtools/docs/USER_GUIDE.md) - Comprehensive usage guide
- [Technical Docs](bibtools/docs/CUSTOM_COMPONENTS.md) - Architecture and API reference
- [Full README](bibtools/README.md) - Complete utilities documentation

### 1. CSV to BibTeX Converter

Convert Springer CSV exports to clean BibTeX format with automatic author name fixing.

**Features:**
*   Automatic author name separation (e.g., "JohnSmithMaryJones" → "John Smith and Mary Jones")
*   Compound name protection (McDonald, O'Brien, MacArthur)
*   File splitting for Zotero compatibility (49 entries per file)
*   Dual interface: CLI and web

### 2. Article Extraction Tool

Extract DOI, Title, and Abstract from academic CSV files for systematic review screening.

**Features:**
*   Excel output ready for Google Sheets or Excel
*   DOI extraction from Extra field when DOI field is empty
*   Missing field handling
*   Dual interface: CLI and web

### 3. Zotero DOI Updater

Update missing DOIs in your Zotero library by extracting them from the Extra field.

**Features:**
*   Connects to user or group libraries
*   Dry-run mode to preview changes
*   Batch processing with progress tracking
*   Preserves existing Extra field content

### 4. Zotero Item Reclassifier

Correct item types in your Zotero library (e.g., preprint → journal article).

**Features:**
*   Flexible reclassification rules
*   Dry-run mode to preview changes
*   Batch processing with detailed logging
*   Preserves all item metadata

### Quick Start - Optional Utilities

**Prerequisites for Zotero tools:**
```bash
export ZOTERO_API_KEY="your_api_key"
export ZOTERO_LIBRARY_ID="12345"
export ZOTERO_LIBRARY_TYPE="group"  # or "user"
```

**CSV to BibTeX Converter:**
```bash
# Web interface
python -m bibtools.web.app
# Open: http://127.0.0.1:5000

# CLI with author fixing (recommended)
python -m bibtools.cli.main --input bibtools/data/input/SearchResults.csv --fix-authors
```

**Article Extraction:**
```bash
# Web interface
python -m bibtools.web.app
# Open: http://127.0.0.1:5000/extract-articles

# CLI
python -m bibtools.cli.extract_articles --input bibtools/data/input/articles.csv --output results/screening.xlsx
```

**Zotero DOI Updater:**
```bash
# Dry run (preview changes)
python -m bibtools.cli.update_zotero_dois --dry-run

# Update DOIs
python -m bibtools.cli.update_zotero_dois
```

**Zotero Item Reclassifier:**
```bash
# Dry run (preview changes)
python -m bibtools.cli.reclassify_zotero_items --from-type preprint --to-type journalArticle --dry-run

# Reclassify items
python -m bibtools.cli.reclassify_zotero_items --from-type preprint --to-type journalArticle
```

### Example

**Input (Springer CSV):**
```csv
Item Title,Authors,Publication Year,...
"Machine Learning Applications",JohnSmithMaryJones,2023,...
```

**Output (BibTeX with fixed authors):**
```bibtex
@article{Smith_2023_Machine,
  title = {Machine Learning Applications},
  author = {John Smith and Mary Jones},
  year = {2023},
  ...
}
```

### Testing

```bash
# Run all tests
pytest bibtools/tests/

# Run specific test categories
pytest -m unit        # Unit tests only
pytest -m property    # Property-based tests
pytest -m web         # Web interface tests

# Run with coverage
pytest bibtools/tests/ --cov=bibtools --cov-report=html
```

### Documentation

*   [Architecture Guide](bibtools/docs/ARCHITECTURE.md) - Detailed project structure and design principles
*   [Custom Components](bibtools/docs/CUSTOM_COMPONENTS.md) - Component documentation

---

## Attribution

**Original paper2zotero project:**
- Author: [ORIGINAL_AUTHOR_NAME]
- Repository: [ORIGINAL_REPO_URL]
- License: MIT

**Custom utilities (`bibtools/` folder):**
- Author: Evelin Limeira
- License: MIT

Both components are licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Contributing

Contributions to bibtools are welcome! Please:
1. Focus contributions on the `bibtools/` folder
2. For issues with paper2zotero core functionality, please refer to the original repository
3. Open issues or pull requests for bugs or enhancements to bibtools

---

## License

MIT License. See [LICENSE](LICENSE) for details.