# Bibtools - Academic Reference Utilities

Standalone tools for advanced academic reference workflows. These utilities are independent from the main paper2zotero tool and can be used separately.

## Tools

### 1. CSV to BibTeX Converter
Convert Springer CSV files to BibTeX format with automatic author name fixing.

### 2. Article Extraction Tool
Extract DOI, Title, and Abstract from academic CSV files for systematic review screening.

### 3. Zotero DOI Updater
Update missing DOIs in your Zotero library by extracting them from the Extra field.

### 4. Zotero Item Reclassifier
Correct item types in your Zotero library based on CSV data.

### 5. Abstract Fetcher
Fetch missing abstracts from multiple academic APIs and update your Zotero library.

## Quick Start

### CSV to BibTeX Converter

**Web Interface:**
```bash
python -m custom.web.app
# Open: http://127.0.0.1:5000
```

**Command Line:**
```bash
python -m custom.cli.main --input data/input/SearchResults.csv --fix-authors
```

### Article Extraction Tool

**Web Interface:**
```bash
python -m custom.web.app
# Open: http://127.0.0.1:5000/extract-articles
```

**Command Line:**
```bash
python -m custom.cli.extract_articles --input data/input/articles.csv --output results/screening.xlsx
```

### Zotero DOI Updater

**Prerequisites:**
```bash
export ZOTERO_API_KEY="your_api_key"
export ZOTERO_LIBRARY_ID="12345"
export ZOTERO_LIBRARY_TYPE="group"  # or "user"
```

**Command Line (Dry Run):**
```bash
python -m custom.cli.update_zotero_dois --dry-run
```

**Command Line (Update):**
```bash
python -m custom.cli.update_zotero_dois
```

### Zotero Item Reclassifier

**Command Line (Dry Run):**
```bash
python -m bibtools.cli.reclassify_zotero_items \
  --api-key YOUR_KEY \
  --library-id YOUR_ID \
  --library-type group \
  --csv bibtools/data/input/SearchResults.csv \
  --collection COLLECTION_ID \
  --dry-run
```

**Command Line (Reclassify):**
```bash
python -m bibtools.cli.reclassify_zotero_items \
  --api-key YOUR_KEY \
  --library-id YOUR_ID \
  --library-type group \
  --csv bibtools/data/input/SearchResults.csv \
  --collection COLLECTION_ID
```

### Abstract Fetcher

**Command Line (Dry Run):**
```bash
python -m bibtools.cli.fetch_abstracts \
  --api-key YOUR_KEY \
  --library-id YOUR_ID \
  --library-type group \
  --collection COLLECTION_ID \
  --springer-api-key YOUR_SPRINGER_KEY \
  --limit 10000 \
  --dry-run
```

**Command Line (Fetch):**
```bash
python -m bibtools.cli.fetch_abstracts \
  --api-key YOUR_KEY \
  --library-id YOUR_ID \
  --library-type group \
  --collection COLLECTION_ID \
  --springer-api-key YOUR_SPRINGER_KEY \
  --limit 10000
```

### Help
```bash
python -m bibtools.cli.main --help
python -m bibtools.cli.extract_articles --help
python -m bibtools.cli.update_zotero_dois --help
python -m bibtools.cli.reclassify_zotero_items --help
python -m bibtools.cli.fetch_abstracts --help
```

## Documentation

- **[Quick Start (5 min)](docs/QUICK_START.md)** - Get started quickly
- **[User Guide](docs/USER_GUIDE.md)** - Comprehensive usage guide
- **[Abstract Fetching Guide](docs/ABSTRACT_FETCHING_GUIDE.md)** - How to fetch missing abstracts
- **[Technical Docs](docs/CUSTOM_COMPONENTS.md)** - Architecture and API reference
- **[Utility Scripts](utils/scripts/README.md)** - Development and debugging tools

## What they do

### CSV to BibTeX Converter
1. Converts Springer CSV exports to BibTeX format
2. Automatically fixes concatenated author names
3. Splits large files into parts (49 entries each)
4. Preserves compound names (McDonald, O'Brien, etc.)

### Article Extraction Tool
1. Extracts DOI, Title, and Abstract from CSV files
2. Extracts DOIs from Extra field when DOI field is empty
3. Generates Excel spreadsheets for screening
4. Handles missing fields gracefully
5. Preserves record order and special characters

### Zotero DOI Updater
1. Connects to your Zotero library (user or group)
2. Finds items without DOIs
3. Extracts DOIs from the Extra field
4. Updates the DOI field in Zotero
5. Supports dry-run mode to preview changes

### Zotero Item Reclassifier
1. Connects to your Zotero library (user or group)
2. Reads CSV file with correct item types
3. Matches items by DOI
4. Updates item types based on CSV "Content Type" field
5. Supports dry-run mode to preview changes

### Abstract Fetcher
1. Connects to your Zotero library (user or group)
2. Finds items without abstracts
3. Searches multiple academic APIs (Springer, OpenAlex, CrossRef, Semantic Scholar, Europe PMC)
4. Scrapes publisher pages as fallback
5. Updates abstracts in Zotero
6. Supports dry-run mode to preview changes

## Structure

```
bibtools/
├── cli/                                  # Command-line interfaces
│   ├── main.py                          # CSV to BibTeX converter CLI
│   ├── extract_articles.py              # Article extraction CLI
│   ├── update_zotero_dois.py            # Zotero DOI updater CLI
│   ├── reclassify_zotero_items.py       # Zotero item reclassifier CLI
│   └── fetch_abstracts.py               # Abstract fetcher CLI
├── core/                                 # Business logic
│   ├── csv_converter.py                 # CSV to BibTeX conversion
│   ├── author_fixer.py                  # Author name fixing
│   ├── article_extractor.py             # Article extraction
│   ├── zotero_doi_updater.py            # Zotero DOI updater
│   ├── zotero_item_reclassifier.py      # Zotero item reclassifier
│   └── models.py                        # Data models
├── web/                                  # Web interface (Flask)
│   ├── app.py                           # Web server with tools
│   └── templates/                       # HTML templates
├── utils/                                # Utilities
│   ├── file_handler.py                  # File operations
│   ├── security.py                      # Security utilities
│   └── scripts/                         # Development/debugging scripts
│       ├── check_zotero_collection.py   # List Zotero collections
│       ├── check_item_types.py          # Check item type distribution
│       └── check_abstracts_status.py    # Check abstract availability
├── docs/                                 # Documentation
│   ├── QUICK_START.md                   # Quick start guide
│   ├── USER_GUIDE.md                    # User guide
│   ├── ABSTRACT_FETCHING_GUIDE.md       # Abstract fetching guide
│   └── CUSTOM_COMPONENTS.md             # Technical documentation
├── data/                                 # Data files
│   └── input/                           # Input CSV files
└── tests/                                # Test suite
```

## Features

- Two interfaces: Web and CLI
- CSV to BibTeX conversion with automatic author fixing
- Article extraction for systematic reviews with DOI extraction from Extra field
- Zotero DOI updater for fixing missing DOIs in your library
- Zotero item reclassifier for correcting item types based on CSV data
- Abstract fetcher with 6 academic API sources (Springer, OpenAlex, CrossRef, Semantic Scholar, Europe PMC, DOI.org scraping)
- File validation and security
- Robust error handling
- Comprehensive tests (132+ tests)
- Development utilities for debugging
- No dependencies on main project

## Testing

```bash
pytest bibtools/tests/
```

## Dependencies

**Core:** Python standard library only

**Web interface:**
```bash
pip install flask
```

**Zotero tools:**
```bash
pip install requests
```

**Tests:**
```bash
pip install pytest hypothesis bibtexparser
```

## Installation

```bash
# Install bibtools package
pip install -e bibtools/

# Or install with all dependencies
pip install -e bibtools/[all]
```

## Examples

### CSV to BibTeX Converter

**Input (CSV):**
```csv
Item Title,Authors,Publication Year
"AI Security",JohnSmithMaryJones,2024
```

**Output (BibTeX):**
```bibtex
@article{Smith_2024_AI,
  title = {AI Security},
  author = {John Smith and Mary Jones},
  year = {2024},
  publisher = {Springer}
}
```

### Article Extraction Tool

**Input (CSV):**
```csv
DOI,Title,Abstract Note
10.1007/test,"Machine Learning","This paper explores ML applications..."
```

**Output (Excel):**
| DOI | Title | Abstract |
|-----|-------|----------|
| 10.1007/test | Machine Learning | This paper explores ML applications... |

## License

MIT License - See [LICENSE](../LICENSE) for details.
