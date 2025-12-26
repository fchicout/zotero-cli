# User Guide - Custom Tools

This comprehensive guide shows you how to use the custom tools for academic CSV processing:
1. **CSV to BibTeX Converter** - Convert Springer CSV to BibTeX with author fixing
2. **Article Extraction Tool** - Extract DOI, Title, and Abstract for systematic reviews

**New to these tools?** Start with the [Quick Start Guide](QUICK_START.md) for a 5-minute introduction.

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
python -m bibtools.web.app
```

### How to use

1. **Open your browser** at: http://127.0.0.1:5000

2. **Upload** your CSV file:
   - Click "Choose CSV file" or
   - Drag and drop the file into the designated area

3. **Click** "Convert to BibTeX"

4. **Download** the generated files

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
python -m bibtools.cli.main convert --input FILE.csv [--output-dir DIRECTORY] [--output-name NAME] [--no-split]
```

### Practical examples

#### 1. Basic conversion (without author fixing)

```bash
python -m bibtools.cli.main convert --input bibtools/data/input/SearchResults.csv
```

#### 2. Basic conversion (split files)

```bash
python -m bibtools.cli.main convert --input bibtools/data/input/SearchResults.csv
```

#### 3. Create a single file (no splitting)

```bash
python -m bibtools.cli.main convert --input bibtools/data/input/SearchResults.csv --no-split
```

#### 4. Specify output directory

```bash
python -m bibtools.cli.main convert --input bibtools/data/input/SearchResults.csv --output-dir my_bibtex
```

#### 5. Custom output name

```bash
python -m bibtools.cli.main convert --input bibtools/data/input/SearchResults.csv --output-name "my_results"
```

#### 6. Process file from another location

```bash
python -m bibtools.cli.main convert --input C:\Downloads\papers.csv --output-dir C:\Documents\bibtex
```

**Note:** Author names are automatically fixed during conversion (concatenated names are separated).

### Available arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--input` | ✅ Yes | - | Path to input CSV file |
| `--output-dir` | ❌ No | `bibtools/data/output` | Directory to save BibTeX files |
| `--output-name` | ❌ No | Input filename | Base name for output files |
| `--no-split` | ❌ No | `False` | Create a single file instead of splitting |

### View help

```bash
python -m bibtools.cli.main convert --help
```

---

## File Structure

### Input

Place your CSV files in:
```
bibtools/data/input/
```

### Output

BibTeX files are generated in:
```
bibtools/data/output/
```

**Generated file types:**
- `springer_results_raw_part1.bib` - Split files (49 entries each)
- `springer_results_raw_part2.bib` - Split files continued
- `springer_results_raw.bib` - Single file (with `--no-split`)
- `my_results.bib` - Custom name (with `--output-name "my_results"`)

---

## What does the converter do?

### Step 1: CSV → BibTeX Conversion
- Reads the CSV file exported from Springer
- Converts each entry to BibTeX format
- Generates unique keys (format: `LastName_Year_TitleWord`)
- **Automatically fixes concatenated author names** (e.g., `JohnSmithMaryJones` → `John Smith and Mary Jones`)
- Preserves compound names: `McDonald`, `O'Brien`, `MacArthur`
- By default, splits into files of 49 entries (Zotero compatible)
- With `--no-split`, creates a single file with all entries

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
for file in bibtools/data/input/*.csv; do
    python -m bibtools.cli.main convert --input "$file"
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
ls bibtools/data/input/SearchResults.csv
```

### "Permission denied"
Run with appropriate permissions or choose another output directory.

### Port 5000 already in use (Web)
Another process is using the port. Kill the process or edit `bibtools/web/app.py` to use another port:
```python
app.run(debug=True, host='0.0.0.0', port=5001)
```

---

## Complete Documentation

For more details, see:
- [QUICK_START.md](QUICK_START.md) - 5-minute quick start guide
- [CUSTOM_COMPONENTS.md](CUSTOM_COMPONENTS.md) - Technical documentation and API reference
- [../README.md](../README.md) - Project overview

---

## Recommended Workflow

1. **Export** your Springer results as CSV
2. **Place** the file in `bibtools/data/input/`
3. **Run** the converter:
   ```bash
   python -m bibtools.cli.main convert --input bibtools/data/input/SearchResults.csv --fix-authors
   ```
4. **Find** the files in `bibtools/data/output/` (use the ones with `_fixed` suffix)
5. **Import** into Zotero or your reference manager

---

**Ready to start?** Choose your preferred option and convert your files!


---

## Tool 2: Article Extraction for Systematic Reviews

Extract DOI, Title, and Abstract from academic CSV files to create Excel spreadsheets for systematic review screening.

### Option 1: Web Interface (Recommended)

#### How to start

```bash
python -m bibtools.web.app
```

#### How to use

1. **Open your browser** at: http://127.0.0.1:5000/extract-articles

2. **Upload** your CSV file:
   - Click "Choose CSV file" or
   - Drag and drop the file into the designated area

3. **Click** "Extract Articles"

4. **Download** the generated Excel file

#### Features

- ✅ User-friendly visual interface
- ✅ Real-time file validation
- ✅ Progress indicator
- ✅ Direct Excel file download
- ✅ Automatic extraction and formatting
- ✅ 50MB file size limit

#### To stop the server

Press `Ctrl+C` in the terminal

---

### Option 2: Command Line (CLI)

#### Basic syntax

```bash
python -m bibtools.cli.extract_articles [--input FILE.csv] [--output FILE.xlsx]
```

#### Practical examples

##### 1. Basic extraction (with default paths)

```bash
python -m bibtools.cli.extract_articles
```

Default paths:
- Input: `bibtools/data/input/z_raw_springer.csv`
- Output: `bibtools/data/output/screening_data.xlsx`

##### 2. Custom input file

```bash
python -m bibtools.cli.extract_articles --input data/input/my_articles.csv
```

##### 3. Custom input and output

```bash
python -m bibtools.cli.extract_articles --input bibtools/data/input/articles.csv --output bibtools/data/output/screening.xlsx
```

##### 4. Process file from another location

```bash
python -m bibtools.cli.extract_articles --input C:\Downloads\papers.csv --output C:\Documents\screening.xlsx
```

#### Available arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--input` or `-i` | ❌ No | `bibtools/data/input/z_raw_springer.csv` | Path to input CSV file |
| `--output` or `-o` | ❌ No | `bibtools/data/output/screening_data.xlsx` | Path for output Excel file |

#### View help

```bash
python -m bibtools.cli.extract_articles --help
```

---

### What does the article extractor do?

#### Step 1: CSV Reading
- Reads the CSV file exported from Springer or other academic databases
- Validates that required columns exist (DOI, Title, Abstract Note)
- Handles missing fields gracefully (empty strings)

#### Step 2: Data Extraction
- Extracts only the essential fields: DOI, Title, Abstract
- Preserves the order of records from the input file
- Handles special characters and encoding correctly

#### Step 3: Excel Generation
- Creates an Excel workbook with three columns
- Adds a header row: DOI | Title | Abstract
- Writes all extracted records
- Saves to the specified output path

---

### Output Example

#### Input (Springer CSV)
```csv
DOI,Title,Abstract Note,Publication Title,Authors,URL,Publication Year
10.1007/test1,"Machine Learning Applications","This paper explores ML in healthcare...","Journal of AI","John Smith",https://example.com,2023
10.1007/test2,"Deep Learning Methods","A comprehensive study of DL...","AI Conference","Jane Doe",https://example.com,2024
```

#### Output (Excel)
| DOI | Title | Abstract |
|-----|-------|----------|
| 10.1007/test1 | Machine Learning Applications | This paper explores ML in healthcare... |
| 10.1007/test2 | Deep Learning Methods | A comprehensive study of DL... |

---

### Usage Tips for Article Extraction

#### When to use the Web Interface?
- ✅ Occasional extractions
- ✅ Preference for visual interface
- ✅ Small/medium files (up to 50MB)
- ✅ No automation needed

#### When to use the CLI?
- ✅ Frequent extractions
- ✅ Very large files (no size limit)
- ✅ Automation and scripts
- ✅ Batch processing
- ✅ Integration with other commands

#### Automation example (CLI)

```bash
# Process all CSVs in a folder
for file in bibtools/data/input/*.csv; do
    python -m bibtools.cli.extract_articles --input "$file" --output "bibtools/data/output/$(basename "$file" .csv)_screening.xlsx"
done
```

---

### Common Issues for Article Extraction

#### "File not found"
Check if the file path is correct:
```bash
# Windows
dir data\input\z_raw_springer.csv

# Linux/Mac
ls bibtools/data/input/z_raw_springer.csv
```

#### "Missing required columns"
The CSV must have these columns:
- `DOI`
- `Title`
- `Abstract Note`

If your CSV has different column names (e.g., "Item Title" instead of "Title"), you'll need to rename them or adjust the CSV before processing.

#### "Empty file"
The CSV must contain at least one data row (not just headers).

#### "Permission denied"
Run with appropriate permissions or choose another output directory.

---

### Recommended Workflow for Systematic Reviews

1. **Export** your search results from Springer as CSV
2. **Place** the file in `data/input/`
3. **Run** the extractor:
   ```bash
   python -m bibtools.cli.extract_articles --input bibtools/data/input/SearchResults.csv
   ```
4. **Find** the Excel file in `bibtools/data/output/`
5. **Open** in Excel or Google Sheets for screening
6. **Add** additional columns for your screening criteria (Include/Exclude, Notes, etc.)

---

## Choosing the Right Tool

### Use CSV to BibTeX Converter when:
- ✅ You need BibTeX files for LaTeX or reference managers
- ✅ You want to fix concatenated author names
- ✅ You're importing into Zotero or other bibliography tools

### Use Article Extraction Tool when:
- ✅ You're conducting a systematic review
- ✅ You need to screen articles in Excel/Google Sheets
- ✅ You only need DOI, Title, and Abstract
- ✅ You want a simple spreadsheet format

---

**Ready to start?** Choose your tool and preferred interface!
