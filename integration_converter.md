# Integration: CSV to BibTeX Converter

## Overview

This document describes the integration of a standalone CSV to BibTeX converter (`csv_to_bibtex.py`) into the paper2zotero project. This tool provides an alternative workflow for users who need to convert Springer search results directly to BibTeX format without using the Zotero API.

## New Functionality

### File: `csv_to_bibtex.py`

A standalone Python script that converts Springer search results CSV files into properly formatted BibTeX files.

**Key Features:**
- Converts Springer CSV exports to BibTeX format
- Automatically splits large result sets into multiple files (50 entries per file)
- Generates unique BibTeX keys using format: `LastName_Year_FirstWord`
- Handles special characters and HTML entities
- Maps Springer content types to appropriate BibTeX entry types
- Preserves DOI, URL, journal, volume, and issue information

**Supported Entry Types:**
- `@article` - for journal articles and reviews
- `@inproceedings` - for conference papers
- `@book` - for books
- `@misc` - for other content types

## Usage

### Basic Usage

```bash
python csv_to_bibtex.py
```

By default, the script looks for `SearchResults (1).csv` and outputs to `springer_results.bib` (or multiple files if needed).

### Customization

Edit the script's main section to customize:

```python
if __name__ == "__main__":
    input_csv = "your_file.csv"           # Input CSV file
    output_base = "output_name"            # Output base name
    entries_per_file = 50                  # Entries per file
```

### Expected CSV Format

The script expects Springer CSV exports with the following columns:
- `Item Title` (required)
- `Authors`
- `Publication Year`
- `Item DOI`
- `URL`
- `Content Type`
- `Publication Title`
- `Book Series Title`
- `Journal Volume`
- `Journal Issue`

## Integration with Existing Project

### Relationship to paper2zotero

This tool complements the existing paper2zotero infrastructure:

1. **paper2zotero** (main project): Full-featured tool for importing papers to Zotero
   - Uses Zotero API
   - Supports multiple sources (arXiv, IEEE, Springer, BibTeX, RIS)
   - Requires Zotero setup and API credentials

2. **csv_to_bibtex.py** (this addition): Lightweight converter
   - No dependencies on Zotero
   - Standalone script
   - Quick conversion for users who only need BibTeX output

### Use Cases

**Use csv_to_bibtex.py when:**
- You need BibTeX files for LaTeX documents
- You don't have Zotero configured
- You want a quick conversion without API setup
- You're working with Springer CSV exports specifically

**Use paper2zotero when:**
- You want to import papers directly to Zotero
- You need to process multiple source formats
- You want the full feature set and integration

## Technical Details

### Text Processing

The converter includes several text processing functions:

- `clean_text()`: Normalizes Unicode, decodes HTML entities, handles special dashes
- `escape_bibtex_special_chars()`: Escapes LaTeX special characters (&, %, $, #, _, {, })
- `format_authors_simple()`: Preserves original author formatting from Springer

### BibTeX Key Generation

Keys are generated using the pattern: `LastName_Year_FirstWord`

Example: `Smith_2023_Machine` for a paper by Smith et al. (2023) titled "Machine Learning Applications"

Duplicate keys are automatically handled by appending numbers: `Smith_2023_Machine1`, `Smith_2023_Machine2`, etc.

### File Splitting

Large result sets are automatically split into multiple files to improve manageability:
- Default: 50 entries per file
- Files named: `output_base_part1.bib`, `output_base_part2.bib`, etc.
- Single file if total entries ≤ 50

## Known Limitations

1. **Author Formatting**: Springer concatenates author names without clear separators. The converter preserves the original format, but manual review may be needed for proper BibTeX author formatting.

2. **Springer-Specific**: Currently optimized for Springer CSV format. Other publishers' CSV formats may require modifications.

3. **No Deduplication**: The script doesn't check for duplicate entries across multiple CSV files.

## Future Enhancements

Potential improvements for better integration:

1. Add as a module to the paper2zotero package structure
2. Create a CLI command in the main paper2zotero interface
3. Support additional CSV formats (IEEE, ACM, etc.)
4. Add author name parsing for better formatting
5. Implement cross-file deduplication
6. Add configuration file support

## Contributing

When contributing improvements to this converter:

1. Maintain backward compatibility with existing CSV format
2. Add tests in the `tests/` directory
3. Update this documentation
4. Follow the project's code style (see existing modules in `src/paper2zotero/`)

## Questions or Issues

For questions about:
- **This converter**: Open an issue describing the CSV format problem
- **Zotero integration**: Refer to the main paper2zotero documentation
- **General usage**: Check the main README.md

---

**Note**: This is a contributed addition to the paper2zotero project, providing an alternative workflow for users who need direct CSV to BibTeX conversion.
