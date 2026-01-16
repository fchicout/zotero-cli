# Command: `tag`

Manage the tag taxonomy across the library.

## Verbs

### `list`
List all unique tags present in the library.

**Usage:**
```bash
zotero-cli tag list
```

---

### `add`
Add one or more tags to a specific item.

**Usage:**
```bash
zotero-cli tag add --item "ITEMKEY" --tags "tag1, tag2"
```

---

### `remove`
Remove one or more tags from a specific item.

**Usage:**
```bash
zotero-cli tag remove --item "ITEMKEY" --tags "tag1"
```

---

### `rename`
Rename an existing tag across the entire library.

**Usage:**
```bash
zotero-cli tag rename --old "old-tag" --new "new-tag"
```

---

### `purge`
Permanently delete specific tags from the entire library.

**Usage:**
```bash
zotero-cli tag purge "old-tag, draft"
```
