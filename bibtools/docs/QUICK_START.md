# Quick Start - 5 Minutes to Success

Get started with the custom tools for academic CSV processing in under 5 minutes.

## Prerequisites

```bash
pip install flask openpyxl
```

---

## Web Interface (Easiest)

Start the web server and use both tools through your browser:

```bash
python -m bibtools.web.app
```

Then open your browser:
- **CSV to BibTeX Converter**: http://localhost:5000
- **Article Extraction**: http://localhost:5000/extract-articles

Upload your CSV file, click convert/extract, and download the results!

---

## Command Line Interface

### CSV to BibTeX Converter

Convert Springer CSV to BibTeX with automatic author name fixing:

```bash
python -m bibtools.cli.main --input data/input/SearchResults.csv --fix-authors
```

**Output**: BibTeX files in `data/output/` with `_fixed` suffix

### Article Extraction Tool

Extract DOI, Title, and Abstract for systematic review screening:

```bash
python -m bibtools.cli.extract_articles --input data/input/articles.csv
```

**Output**: Excel file in `data/output/screening_data.xlsx`

---

## What Each Tool Does

### CSV to BibTeX Converter
- Converts Springer CSV → BibTeX format
- Fixes concatenated author names (e.g., "JohnSmithMaryJones" → "John Smith and Mary Jones")
- Splits large files (49 entries per file)
- Perfect for importing into Zotero or LaTeX

### Article Extraction Tool
- Extracts DOI, Title, Abstract from CSV
- Generates Excel spreadsheet
- Perfect for systematic review screening in Excel/Google Sheets

---

## Example Workflows

### For Bibliography Management
```bash
# 1. Export CSV from Springer
# 2. Convert to BibTeX
python -m bibtools.cli.main --input data/input/SearchResults.csv --fix-authors

# 3. Import the *_fixed.bib files into Zotero
```

### For Systematic Reviews
```bash
# 1. Export CSV from Springer
# 2. Extract articles
python -m bibtools.cli.extract_articles --input data/input/SearchResults.csv

# 3. Open screening_data.xlsx in Excel/Google Sheets
# 4. Add your screening columns (Include/Exclude, Notes, etc.)
```

---

## Need More Help?

- **Detailed Usage Guide**: See [USER_GUIDE.md](USER_GUIDE.md) for comprehensive examples, troubleshooting, and automation
- **Technical Documentation**: See [CUSTOM_COMPONENTS.md](CUSTOM_COMPONENTS.md) for architecture and API reference
- **Project Overview**: See [../README.md](../README.md) for general information

---

## Quick Troubleshooting

**"No module named 'flask'"**
```bash
pip install flask openpyxl
```

**"File not found"**
- Check the file path is correct
- Use absolute paths if relative paths don't work

**"Port 5000 already in use"**
- Another process is using the port
- Kill the process or change the port in `bibtools/web/app.py`

**"Missing required columns"** (Article Extraction)
- CSV must have: `DOI`, `Title`, `Abstract Note`
- Rename columns in your CSV if they have different names

---

**That's it!** You're ready to start converting and extracting. For more advanced usage, check out the [USER_GUIDE.md](USER_GUIDE.md).
