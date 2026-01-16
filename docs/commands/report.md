# Command: `report`

Generate statistics, PRISMA diagrams, and immutable snapshots.

## Verbs

### `prisma`
Generate a PRISMA-aligned screening summary.

**Usage:**
```bash
zotero-cli report prisma --collection "SLR" --output-chart "prisma.png"
```

**Parameters:**
*   `--collection`: (Required) Collection name or key.
*   `--output-chart`: Optional path to save a Mermaid-rendered chart.

---

### `snapshot`
Generate an immutable JSON audit trail of all items in a collection, including full metadata and child notes.

**Usage:**
```bash
zotero-cli report snapshot --collection "Included" --output "snapshot_v1.json"
```

---



### `screening`

Generate a detailed Markdown report of the screening process, including PRISMA statistics and a Mermaid flow diagram.



**Usage:**

```bash

zotero-cli report screening --collection "SLR" --output "screening_report.md"

```



---



### `status`

Generate a real-time Markdown progress dashboard for a collection.



**Usage:**

```bash

zotero-cli report status --collection "SLR" --output "progress.md"

```
