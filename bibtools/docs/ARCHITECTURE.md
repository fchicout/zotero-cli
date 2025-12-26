# Project Architecture

## Overview

This project provides tools for working with academic CSV files:
1. **CSV to BibTeX Converter** - Convert Springer CSV exports to BibTeX format with automatic author name fixing
2. **Article Extraction Tool** - Extract DOI, Title, and Abstract for systematic review screening

The code follows clean architecture principles with clear separation between business logic, CLI, and web interfaces.

## Directory Structure

```
csv2bib/
├── bibtools/                      # Custom tools for academic CSV processing
│   ├── core/                    # Business logic
│   │   ├── models.py           # Data models (BibTeXEntry, ArticleData, etc.)
│   │   ├── csv_converter.py    # CSV to BibTeX conversion
│   │   ├── author_fixer.py     # Author name fixing logic
│   │   └── article_extractor.py # Article extraction for screening
│   │
│   ├── cli/                     # Command-line interfaces
│   │   ├── main.py             # CSV to BibTeX converter CLI
│   │   └── extract_articles.py # Article extraction CLI
│   │
│   ├── web/                     # Web interface
│   │   ├── app.py              # Flask web server (both tools)
│   │   ├── static/             # CSS/JS assets
│   │   └── templates/          # HTML templates
│   │       ├── index.html      # BibTeX converter page
│   │       └── extract_articles.html # Article extraction page
│   │
│   └── utils/                   # Shared utilities
│       ├── file_handler.py     # File I/O operations
│       └── security.py         # Security utilities
│
├── tests_bibtools/                # Tests for custom code
│   ├── test_csv_converter.py
│   ├── test_author_fixer.py
│   ├── test_cli.py
│   ├── test_web_interface.py
│   └── fixtures/               # Test data
│
├── data/                        # Data directories
│   ├── input/                  # Place your CSV files here
│   ├── output/                 # Generated files (BibTeX, Excel)
│   └── temp/                   # Temporary files
│
└── docs/                        # Documentation
    ├── QUICK_START.md          # 5-minute quick start
    ├── USER_GUIDE.md           # Comprehensive usage guide
    ├── CUSTOM_COMPONENTS.md    # Technical documentation
    └── ARCHITECTURE.md         # This file
```

## Core Components

### 1. CSV Converter (`bibtools/core/csv_converter.py`)

Converts Springer CSV files to BibTeX format.

**Key features:**
- Parses Springer CSV exports
- Generates unique BibTeX keys
- Splits large files (49 entries per file)
- Handles special characters and HTML entities

### 2. Author Fixer (`bibtools/core/author_fixer.py`)

Fixes concatenated author names from Springer exports.

**Key features:**
- Separates concatenated names (e.g., "JohnSmithMaryJones" → "John Smith and Mary Jones")
- Protects compound names (McDonald, O'Brien, MacArthur)
- Preserves special characters and formatting

### 3. Article Extractor (`bibtools/core/article_extractor.py`)

Extracts DOI, Title, and Abstract from academic CSV files for systematic review screening.

**Key features:**
- Extracts essential fields from Springer CSV exports
- Generates Excel spreadsheets (.xlsx format)
- Handles missing fields gracefully
- Preserves record order and special characters
- Comprehensive error handling with detailed messages

### 4. CLI Interfaces

**CSV to BibTeX Converter** (`bibtools/cli/main.py`):
```bash
python -m bibtools.cli.main convert --input data/input/SearchResults.csv --output-dir data/output
```

**Article Extraction Tool** (`bibtools/cli/extract_articles.py`):
```bash
python -m bibtools.cli.extract_articles --input data/input/articles.csv --output results/screening.xlsx
```

### 5. Web Interface (`bibtools/web/app.py`)

Browser-based interface for both tools with easy file upload and download.

**Usage:**
```bash
python -m bibtools.web.app
# Open browser to http://localhost:5000
# - CSV to BibTeX: http://localhost:5000
# - Article Extraction: http://localhost:5000/extract-articles
```

## Workflows

### CSV to BibTeX Conversion

**Using CLI:**
1. Place your Springer CSV file in `data/input/`
2. Run the converter:
   ```bash
   python -m bibtools.cli.main convert --input data/input/SearchResults.csv
   ```
3. Find generated BibTeX files in `data/output/`

**Using Web Interface:**
1. Start the web server:
   ```bash
   python -m bibtools.web.app
   ```
2. Open browser to `http://localhost:5000`
3. Upload your CSV file
4. Download the generated BibTeX files

### Article Extraction for Systematic Reviews

**Using CLI:**
1. Place your Springer CSV file in `data/input/`
2. Run the extractor:
   ```bash
   python -m bibtools.cli.extract_articles --input data/input/articles.csv
   ```
3. Find generated Excel file in `data/output/`

**Using Web Interface:**
1. Start the web server:
   ```bash
   python -m bibtools.web.app
   ```
2. Open browser to `http://localhost:5000/extract-articles`
3. Upload your CSV file
4. Download the generated Excel file

## Data Models

### BibTeXEntry

Represents a single bibliographic entry:
- `key`: Unique identifier (e.g., "Smith_2023_Machine")
- `entry_type`: BibTeX type (article, inproceedings, etc.)
- `title`, `authors`, `year`, `doi`, `url`, `journal`, etc.

### ArticleData

Represents extracted article data for screening:
- `doi`: Digital Object Identifier
- `title`: Article title
- `abstract`: Article abstract
- `to_dict()`: Converts to dictionary for Excel writing

### ConversionResult

Encapsulates conversion outcome:
- `success`: Boolean indicating success
- `entries_count`: Number of entries processed
- `output_files`: List of generated file paths
- `errors`: List of error messages

## Design Principles

1. **Separation of Concerns**: Business logic isolated from I/O and presentation
2. **Single Responsibility**: Each module has one clear purpose
3. **Clean Architecture**: Core logic doesn't depend on external frameworks
4. **Testability**: Comprehensive property-based testing with Hypothesis

## Testing

Tests are located in `tests_bibtools/` and use:
- **pytest**: Test framework
- **Hypothesis**: Property-based testing (100+ iterations per property)

Run tests:
```bash
pytest tests_bibtools/
```

## Related Projects

This project is built alongside **paper2zotero** (in `src/paper2zotero/`), which provides full Zotero integration. The custom tools here focus specifically on CSV to BibTeX conversion without requiring Zotero setup.
