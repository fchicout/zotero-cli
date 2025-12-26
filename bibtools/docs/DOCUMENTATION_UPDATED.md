# Documentation Updated for bibtools

## Summary

All documentation in `bibtools/docs/` has been updated to reflect the new `bibtools` package name.

## Updated Files

✅ **QUICK_START.md** - 5-minute quick start guide  
✅ **USER_GUIDE.md** - Comprehensive usage guide  
✅ **ARCHITECTURE.md** - Project architecture overview  
✅ **CUSTOM_COMPONENTS.md** - Technical documentation and API reference  

## Changes Made

### Module References
- `custom/` → `bibtools/`
- `custom.` → `bibtools.`
- `tests_custom/` → `bibtools/tests/`

### Import Statements
- `from custom` → `from bibtools`
- `import custom` → `import bibtools`

### CLI Commands
- `python -m custom.cli.main` → `python -m bibtools.cli.main`
- `python -m custom.web.app` → `python -m bibtools.web.app`
- `python -m custom.cli.extract_articles` → `python -m bibtools.cli.extract_articles`

### File Paths
- `custom/core/` → `bibtools/core/`
- `custom/cli/` → `bibtools/cli/`
- `custom/web/` → `bibtools/web/`
- `custom/utils/` → `bibtools/utils/`

## Documentation Structure

```
bibtools/docs/
├── QUICK_START.md              # 5-minute quick start
├── USER_GUIDE.md               # Comprehensive usage guide
├── ARCHITECTURE.md             # Project architecture
├── CUSTOM_COMPONENTS.md        # Technical documentation
└── DOCUMENTATION_UPDATED.md    # This file
```

## Quick Links

### For Users
- [Quick Start (5 min)](QUICK_START.md) - Get started quickly
- [User Guide](USER_GUIDE.md) - Comprehensive usage examples

### For Developers
- [Architecture](ARCHITECTURE.md) - Project structure and design
- [Technical Docs](CUSTOM_COMPONENTS.md) - API reference and advanced usage

## Example Commands

### CSV to BibTeX Converter
```bash
# Web interface
python -m bibtools.web.app

# CLI
python -m bibtools.cli.main convert --input bibtools/data/input/SearchResults.csv
```

### Article Extractor
```bash
# Web interface
python -m bibtools.web.app
# Navigate to: http://localhost:5000/extract-articles

# CLI
python -m bibtools.cli.extract_articles --input bibtools/data/input/articles.csv
```

### Zotero Utilities
```bash
# DOI Updater
python -m bibtools.cli.update_zotero_dois --dry-run

# Item Reclassifier
python -m bibtools.cli.reclassify_zotero_items --from-type preprint --to-type journalArticle --dry-run
```

## Verification

All documentation has been tested and verified to use the correct `bibtools` naming throughout.

---

**Last Updated:** December 19, 2025  
**Package:** bibtools v1.0.0  
**Author:** Evelin Limeira
