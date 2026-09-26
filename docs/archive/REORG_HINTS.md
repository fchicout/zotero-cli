# Sullivan's Documentation Hints: The Great v2.0 Reorganization

Sullivan, use this log to track the migration of CLI commands from the legacy v1.x structure to the modern v2.0 workflow-centric structure.

## Command Migration Map

| Legacy Command (v1.x) | New Command (v2.0) | Status | Logic Change |
| :--- | :--- | :--- | :--- |
| `manage move` | `item move` | DONE | Uses new auto-source inference. |
| `inspect` | `item inspect` | DONE | **BREAKING:** Key is now positional (`item inspect <KEY>`). |
| `screen` | `review screen` | DONE | Specifically for Title/Abstract screening TUI. |
| `decide` / `d` | `review decide` | DONE | Grouped under review workflow. Alias `d` supported. |
| `manage clean` | `collection clean` | DONE | Better object-oriented fit. |
| `manage tags` | `tag` (namespace) | DONE | Use `tag list`, `tag purge`. |
| `list items` | `item list` | DONE | Added `--trash` and `--top-only`. |
| `list collections` | `collection list` | DONE | |
| `list groups` | `system groups` | DONE | Centralized in system diagnostics. |
| `info` | `system info` | DONE | |

## New v2.0 Capabilities
*   **`collection create`**: Supports `--parent` for nesting.
*   **`collection rename`**: Smart resolution (accepts Name or ID).
*   **`collection delete`**: Smart resolution + **`--recursive`** flag.
*   **`item update`**: Supports `--doi`, `--title`, and **`--abstract`**.
*   **`tag purge`**: Bulk deletion of multiple tags via chunked API calls.

## Architectural Notes for Docs:
*   **Noun-Verb Pattern:** Standardized on `zotero-cli <noun> <verb>`.
*   **Smart Identifiers:** Collections can be referenced by Name or Key in delete/rename.
*   **Safe Destruction:** Recursive deletion logs every item/sub-folder removed for auditability.
*   **Legacy Routing:** Implementation in `main.py` ensures `zotero-cli decide` still works but warns the user.

## Guardrails:
*   Compatibility aliases emit `stderr` warnings.
*   Version `v1.2.0` is the last legacy LTS. Current dev version is `v2.0.0-dev`.