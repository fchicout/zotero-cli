# Command: `analyze`

Deep analysis and visualization of your research data.

## Verbs

### `audit`
Check a collection for items with missing metadata (DOI, ArXiv ID) or missing PDF attachments.

**Usage:**
```bash
zotero-cli analyze audit --collection "SLR-Core"
```

---

### `lookup`
Perform bulk metadata retrieval for a list of Zotero keys or from a file.

**Usage:**
```bash
zotero-cli analyze lookup --keys "KEY1,KEY2" --fields "title,doi"
```

---

### `graph`
Generate a Mermaid/Graphviz citation graph for one or more collections.

**Usage:**
```bash
zotero-cli analyze graph --collections "Included" > graph.dot
```
