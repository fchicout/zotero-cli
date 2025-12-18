# CSV to BibTeX Converter

Standalone converter for Springer CSV files to BibTeX format with automatic author name fixing.

## Quick Start

### Web Interface
```bash
python -m custom.web.app
```
Open: http://127.0.0.1:5000

### Command Line
```bash
python -m custom.cli.main --input data/input/SearchResults.csv --fix-authors
```

### Help
```bash
python -m custom.cli.main --help
```

## Documentation

See **[QUICK_START.md](QUICK_START.md)** for detailed usage instructions.

## What it does

1. Converts Springer CSV exports to BibTeX format
2. Automatically fixes concatenated author names
3. Splits large files into parts (49 entries each)
4. Preserves compound names (McDonald, O'Brien, etc.)

## Structure

```
custom/
├── cli/              # Command-line interface
├── core/             # Business logic
│   ├── csv_converter.py
│   ├── author_fixer.py
│   └── models.py
├── web/              # Web interface (Flask)
└── utils/            # Utilities
```

## Features

- Two interfaces: Web and CLI
- Automatic author name fixing
- File validation
- Robust error handling
- Comprehensive tests (96 tests)
- No dependencies on main project

## Testing

```bash
pytest tests_custom/
```

## Dependencies

**Core:** Python standard library only

**Web interface:**
```bash
pip install flask
```

**Tests:**
```bash
pip install pytest hypothesis bibtexparser
```

## Example

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

## License

MIT License - See [LICENSE](../LICENSE) for details.
