# Command: `report`

General library analytics and metadata reports.

## Verbs

### `duplicates`
Find and list duplicate items across specified collections, or the whole library if `--collections` is omitted. Matches by DOI, ISBN, ArXiv ID, or normalized title (exact tier), plus a fuzzy year/author/title fallback tier for near-duplicates that don't exactly match — including preprint/published-version pairs, labeled distinctly. Reports which collection each occurrence came from and whether their SDB screening decisions agree (`MATCHING`/`CONFLICTING`/`UNSCREENED`). Read-only — unlike `slr prune`, nothing is modified. `--export-plan` writes a bulk-editable merge plan (`.csv` or `.json`) consumable by `item merge --from-plan`.

**Usage:**
```bash
zotero-cli report duplicates --collections "ColA,ColB"
zotero-cli report duplicates --collections "ColA,ColB" --csv duplicates.csv
zotero-cli report duplicates
zotero-cli report duplicates --export-plan duplicates_plan.csv
```

---

### `audit`
Audits collection metadata completeness (e.g. missing DOIs, abstracts, titles, or PDFs).

**Usage:**
```bash
zotero-cli report audit --collection "My Collection" [--verbose] [--export-missing missing.txt]
```

---

### `verify-latex`
Audits citations in a LaTeX manuscript against Zotero items to ensure they exist and are screened.

**Usage:**
```bash
zotero-cli report verify-latex --latex "manuscript.tex"
```

---

### `stats`
Displays an overview of library item types and counts, publication years, and total authors.

**Usage:**
```bash
zotero-cli report stats [--collection "My Collection"]
```

---

### `attachments`
Analyzes disk usage and missing PDF files in your library or a collection.

**Usage:**
```bash
zotero-cli report attachments [--collection "My Collection"] [--output report.md]
```