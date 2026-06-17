# Command: `report`

General library analytics and metadata reports.

## Verbs

### `duplicates`
Find and list duplicate items across specified collections.

**Usage:**
```bash
zotero-cli report duplicates --collections "ColA,ColB"
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