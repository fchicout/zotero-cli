# Command: `review decide`

Record a screening decision for a single item via CLI.

**Usage:**
```bash
zotero-cli review decide --key ITEM_KEY --vote INCLUDE --code "IC1"
```

**Options:**
*   `--key`: The Zotero Item Key.
*   `--vote`: `INCLUDE` or `EXCLUDE`.
*   `--code`: The criteria code (e.g., IC1, EC2).
*   `--reason`: Optional text description for the decision.
*   `--source`: Optional source collection (for movement).
*   `--target`: Optional target collection (for movement).
*   `--phase`: Screening phase (default: `title_abstract`).

**Exclusion Presets:**
*   `--short-paper CODE`: Shortcut for `--vote EXCLUDE --reason "Short Paper"`.
*   `--not-english CODE`: Shortcut for `--vote EXCLUDE --reason "Not English"`.
*   `--is-survey CODE`: Shortcut for `--vote EXCLUDE --reason "SLR/Survey"`.
*   `--no-pdf CODE`: Shortcut for `--vote EXCLUDE --reason "No PDF"`.
