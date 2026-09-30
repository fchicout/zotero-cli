# Command: `tag`

Manage the tag taxonomy across the library.

## Verbs

### `list`
List all unique tags present in the library.

**Usage:**
```bash
zotero-cli tag list [--format table|json|csv]
```

---

### `add`
Add one or more tags to a specific item.

**Usage:**
```bash
zotero-cli tag add --key "ITEMKEY" --tags "tag1, tag2"
```

---

### `purge`
Remove every tag from every item in a collection. The items themselves are not changed otherwise. Previews by default.

**Usage:**
```bash
zotero-cli tag purge --collection "Imported"             # preview
zotero-cli tag purge --collection "Imported" --execute   # apply
```

There is no command to remove or rename a single tag; use Zotero for that.
