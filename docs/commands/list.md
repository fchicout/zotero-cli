# Command: `list`

Generic listing command for various Zotero objects.

## Verbs

### `items`
List items in a specific collection.

**Usage:**
```bash
zotero-cli list items --collection "My Papers" --top-only
```

**Parameters:**
*   `--collection`: Name or Key of the collection.
*   `--top-only`: Only show top-level items (skip children).
*   `--trash`: List items currently in the trash.

---

### `collections`
Alias for `zotero-cli collection list`.

---

### `groups`
Alias for `zotero-cli system groups`.
