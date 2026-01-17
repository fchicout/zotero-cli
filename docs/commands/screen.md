# Command: `review screen`

Interactive Terminal User Interface (TUI) for screening papers.

**Usage:**
```bash
zotero-cli review screen --source "Raw" --include "Accepted" --exclude "Rejected"
```

**Options:**
*   `--source`: The collection containing items to be screened.
*   `--include`: Target collection for accepted items.
*   `--exclude`: Target collection for rejected items.
*   `--state`: Path to a local CSV file to track progress and decisions locally.
*   `--file`: (Headless mode) Process bulk decisions from a CSV file instead of opening the TUI.

**TUI Keybindings:**
*   `i` or `y`: Include item.
*   `e` or `n`: Exclude item (will prompt for reason code).
*   `s`: Skip item.
*   `q`: Quit session.
