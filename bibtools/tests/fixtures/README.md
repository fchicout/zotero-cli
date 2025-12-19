# Test Fixtures

This directory contains test fixtures used for validating the custom CSV-to-BibTeX conversion code.

## Files

### sample_springer.csv
Sample Springer CSV export data used for behavioral equivalence testing. Contains 3 representative entries with:
- Conference papers and articles
- Concatenated author names (e.g., "Dhruv DaveyKayvan Karim...")
- Various publication types
- Complete bibliographic metadata

### test_authors.bib
BibTeX file with concatenated author names for testing the author fixing functionality.

### test_authors_fixed.bib
Expected output after running the author fixer on test_authors.bib.

### test_authors_fixed_new.bib
Alternative expected output for author fixing tests.

### empty.csv
Empty CSV file for testing error handling when no data is provided.

### malformed.csv
Malformed CSV file with incorrect column structure for testing error handling.

### large_springer.csv
Large CSV file with 21 entries for testing multi-file output generation (files are split at 49 entries per file by default).

## Usage

These fixtures are used by the test suite in `tests_custom/` to validate:

1. **CSV Conversion**: That the refactored CSVConverter produces the same BibTeX output as the original csv_to_bibtex.py script
2. **Author Fixing**: That the refactored AuthorFixer produces the same corrections as the original fix_bibtex_authors_claude.py script
3. **Complete Pipeline**: That the end-to-end conversion process (CSV → BibTeX → Fixed BibTeX) produces equivalent results

## Behavioral Equivalence

The behavioral equivalence tests ensure that the refactored code maintains 100% functional compatibility with the original scripts. This is critical for:

- Preserving existing workflows
- Ensuring no regressions during refactoring
- Validating that the new architecture doesn't change behavior
- Maintaining trust in the conversion process

See `tests_custom/test_behavioral_equivalence.py` for the complete test suite.
