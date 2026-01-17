# Command: `report`

Generate screening statistics, PRISMA flow diagrams, and audit snapshots.

## Verbs

### `prisma`
Generate PRISMA screening statistics and optionally a Mermaid flow diagram.

**Usage:**
```bash
zotero-cli report prisma --collection "SLR-Core" --output-chart prisma.png
```

---

### `snapshot`
Create a JSON snapshot of a collection's current state for auditing and drift detection.

**Usage:**
```bash
zotero-cli report snapshot --collection "Included" --output included_2026.json
```

---

### `screening`
Generate a detailed Markdown report with all screening decisions and reasons.

**Usage:**
```bash
zotero-cli report screening --collection "SLR-Core" --output screening_report.md
```

---

### `status`
Display a real-time progress dashboard of the screening process in the terminal.

**Usage:**
```bash
zotero-cli report status --collection "Raw"
```