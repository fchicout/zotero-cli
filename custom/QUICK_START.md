# Quick Start Guide - CSV to BibTeX Converter

This guide shows you how to use the CSV (Springer) to BibTeX converter with automatic author name fixing.

## Prerequisites

- Python 3.8 or higher
- Flask (only for web interface)

```bash
pip install flask
```

---

## Option 1: Web Interface (Recommended)

### How to start

```bash
python -m custom.web.app
```

### How to use

1. **Open your browser** at: http://127.0.0.1:5000

2. **Upload** your CSV file:
   - Click "Choose CSV file" or
   - Drag and drop the file into the designated area

3. **Click** "Convert to BibTeX"

4. **Download** the generated files (with `_fixed` suffix)

### Features

- ✅ User-friendly visual interface
- ✅ Real-time file validation
- ✅ Progress indicator
- ✅ Direct file download
- ✅ Automatic conversion and fixing
- ✅ 16MB file size limit

### To stop the server

Press `Ctrl+C` in the terminal

---

## Option 2: Command Line (CLI)

### Basic syntax

```bash
python -m custom.cli.main --input FILE.csv [--output-dir DIRECTORY] [--fix-authors]
```

### Practical examples

#### 1. Basic conversion (without author fixing)

```bash
python -m custom.cli.main --input data/input/SearchResults.csv
```

#### 2. Conversion with author fixing (RECOMMENDED)

```bash
python -m custom.cli.main --input data/input/SearchResults.csv --fix-authors
```

#### 3. Specify output directory

```bash
python -m custom.cli.main --input data/input/SearchResults.csv --output-dir my_bibtex --fix-authors
```

#### 4. Process file from another location

```bash
python -m custom.cli.main --input C:\Downloads\papers.csv --output-dir C:\Documents\bibtex --fix-authors
```

### Available arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--input` | ✅ Yes | - | Path to input CSV file |
| `--output-dir` | ❌ No | `data/output` | Directory to save BibTeX files |
| `--fix-authors` | ❌ No | `False` | Enable automatic author name fixing |

### View help

```bash
python -m custom.cli.main --help
```

---

## File Structure

### Input

Place your CSV files in:
```
data/input/
```

### Output

BibTeX files are generated in:
```
data/output/
```

**Generated file types:**
- `springer_results_raw_part1.bib` - Version without fixing
- `springer_results_raw_part1_fixed.bib` - Version with fixed authors

---

## What does the converter do?

### Step 1: CSV → BibTeX Conversion
- Reads the CSV file exported from Springer
- Converts each entry to BibTeX format
- Generates unique keys (format: `LastName_Year_TitleWord`)
- Splits into files of 49 entries (Zotero compatible)

### Step 2: Author Fixing (with `--fix-authors`)
- Detects concatenated names: `JohnSmithMaryJones`
- Separates correctly: `John Smith and Mary Jones`
- Preserves compound names: `McDonald`, `O'Brien`, `MacArthur`
- Keeps hyphens: `Jiun-Yi Yang`

---

## Output Example

### Input (CSV)
```csv
Item Title,Authors,Publication Year
"Machine Learning",JohnSmithMaryJones,2023
```

### Output (Fixed BibTeX)
```bibtex
@article{Smith_2023_Machine,
  title = {Machine Learning},
  author = {John Smith and Mary Jones},
  year = {2023},
  publisher = {Springer}
}
```

---

## Usage Tips

### When to use the Web Interface?
- ✅ Occasional conversions
- ✅ Preference for visual interface
- ✅ Small/medium files (up to 16MB)
- ✅ No automation needed

### When to use the CLI?
- ✅ Frequent conversions
- ✅ Very large files (no size limit)
- ✅ Automation and scripts
- ✅ Batch processing
- ✅ Integration with other commands

### Automation example (CLI)

```bash
# Process all CSVs in a folder
for file in data/input/*.csv; do
    python -m custom.cli.main --input "$file" --fix-authors
done
```

---

## Common Issues

### "No module named 'flask'"
```bash
pip install flask
```

### "File not found"
Check if the file path is correct:
```bash
# Windows
dir data\input\SearchResults.csv

# Linux/Mac
ls data/input/SearchResults.csv
```

### "Permission denied"
Run with appropriate permissions or choose another output directory.

### Port 5000 already in use (Web)
Another process is using the port. Kill the process or edit `custom/web/app.py` to use another port:
```python
app.run(debug=True, host='0.0.0.0', port=5001)
```

---

## Complete Documentation

For more details, see:
- `docs/CUSTOM_COMPONENTS.md` - Complete documentation
- `custom/web/README.md` - Web interface details
- `README.md` - Project overview

---

## Recommended Workflow

1. **Export** your Springer results as CSV
2. **Place** the file in `data/input/`
3. **Run** the converter:
   ```bash
   python -m custom.cli.main --input data/input/SearchResults.csv --fix-authors
   ```
4. **Find** the files in `data/output/` (use the ones with `_fixed` suffix)
5. **Import** into Zotero or your reference manager

---

**Ready to start?** Choose your preferred option and convert your files!
