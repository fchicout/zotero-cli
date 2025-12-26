# Web Interface

Web interface for converting Springer CSV files to BibTeX format.

## Quick Start

```bash
python -m bibtools.web.app
```

Open: http://localhost:5000

## Requirements

```bash
pip install flask
```

## Usage

1. Open http://localhost:5000
2. Upload CSV file (drag-and-drop or click)
3. Click "Convert to BibTeX"
4. Download generated files

## Features

- Drag-and-drop file upload
- Automatic author name fixing
- Multi-file output (49 entries per file)
- 16MB file size limit
- Responsive design

## Troubleshooting

**Port already in use:**
```bash
python -m flask --app bibtools.web.app run --port 5001
```

**Permission errors:**
Ensure write access to `bibtools/data/temp/` and `bibtools/data/output/`
