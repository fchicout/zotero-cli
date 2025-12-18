# Project Architecture

## Overview

This project provides tools to convert Springer CSV exports to BibTeX format with automatic author name fixing. The code follows clean architecture principles with clear separation between business logic, CLI, and web interfaces.

## Directory Structure

```
csv2bib/
├── custom/                      # Custom conversion tools
│   ├── core/                    # Business logic
│   │   ├── models.py           # Data models (BibTeXEntry, ConversionResult)
│   │   ├── csv_converter.py    # CSV to BibTeX conversion
│   │   └── author_fixer.py     # Author name fixing logic
│   │
│   ├── cli/                     # Command-line interface
│   │   └── main.py             # CLI entry point
│   │
│   ├── web/                     # Web interface
│   │   ├── app.py              # Flask web server
│   │   ├── static/             # CSS/JS assets
│   │   └── templates/          # HTML templates
│   │
│   └── utils/                   # Shared utilities
│       └── file_handler.py     # File I/O operations
│
├── tests_custom/                # Tests for custom code
│   ├── test_csv_converter.py
│   ├── test_author_fixer.py
│   └── fixtures/               # Test data
│
├── data/                        # Data directories
│   ├── input/                  # Place your CSV files here
│   ├── output/                 # Generated BibTeX files
│   └── temp/                   # Temporary files
│
└── docs/                        # Documentation
    └── ARCHITECTURE.md         # This file
```

## Core Components

### 1. CSV Converter (`custom/core/csv_converter.py`)

Converts Springer CSV files to BibTeX format.

**Key features:**
- Parses Springer CSV exports
- Generates unique BibTeX keys
- Splits large files (49 entries per file)
- Handles special characters and HTML entities

### 2. Author Fixer (`custom/core/author_fixer.py`)

Fixes concatenated author names from Springer exports.

**Key features:**
- Separates concatenated names (e.g., "JohnSmithMaryJones" → "John Smith and Mary Jones")
- Protects compound names (McDonald, O'Brien, MacArthur)
- Preserves special characters and formatting

### 3. CLI Interface (`custom/cli/main.py`)

Command-line tool for batch processing.

**Usage:**
```bash
python -m custom.cli.main --input data/input/SearchResults.csv --output-dir data/output --fix-authors
```

### 4. Web Interface (`custom/web/app.py`)

Browser-based interface for easy file upload and conversion.

**Usage:**
```bash
python -m custom.web.app
# Open browser to http://localhost:5000
```

## Workflow

### Using CLI

1. Place your Springer CSV file in `data/input/`
2. Run the converter:
   ```bash
   python -m custom.cli.main --input data/input/SearchResults.csv --fix-authors
   ```
3. Find generated BibTeX files in `data/output/`

### Using Web Interface

1. Start the web server:
   ```bash
   python -m custom.web.app
   ```
2. Open browser to `http://localhost:5000`
3. Upload your CSV file
4. Download the generated BibTeX files

## Data Models

### BibTeXEntry

Represents a single bibliographic entry:
- `key`: Unique identifier (e.g., "Smith_2023_Machine")
- `entry_type`: BibTeX type (article, inproceedings, etc.)
- `title`, `authors`, `year`, `doi`, `url`, `journal`, etc.

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

Tests are located in `tests_custom/` and use:
- **pytest**: Test framework
- **Hypothesis**: Property-based testing (100+ iterations per property)

Run tests:
```bash
pytest tests_custom/
```

## Related Projects

This project is built alongside **paper2zotero** (in `src/paper2zotero/`), which provides full Zotero integration. The custom tools here focus specifically on CSV to BibTeX conversion without requiring Zotero setup.
