# Command: `schema`

Prints a machine-readable description of the whole command line as JSON, for scripts and AI agents that would otherwise have to parse `--help`.

## Usage
```bash
zotero-cli schema [COMMAND ...]
```

With no arguments it prints everything; naming a command or group (`schema item list`, `schema slr`) prints just that part. An unknown name exits with status 2.

**Parameters:**
*   `command_path` (shown as `COMMAND`): Optional. A command or group to limit the output to, such as `item list` or `slr`.

## What it contains
The document is generated from the real argument parser, so it can't drift from what the program accepts.

*   `version`, `schema_version` (the layout of this document, currently 1) and `program`.
*   `exit_codes`: every exit status and its meaning, the same table as [EXIT_CODES.md](../EXIT_CODES.md).
*   `global_options`: `--user`, `--offline`, `--config`, `--verbose`.
*   `commands`: the tree of commands. A group has `commands`; a runnable command has:
    *   `path` (for example `["item", "list"]`), `help`, `description`;
    *   `arguments`: each with `name`, `kind` (`option` or `positional`), `flags`, `type` (`string`, `integer`, `number`, `boolean`), `required`, `repeatable`, `default`, `choices` and `help`. Deprecated aliases kept hidden in `--help` are left out;
    *   `effect`: what running it can change: `read` (nothing), `local` (only this machine's own files and state: exports and backups it writes, the job queue, config) or `write` (your Zotero library, or the local `zotero.sqlite`);
    *   `preview_by_default`: true for a `write` command that only shows what it would do until `--execute`;
    *   `deprecated`: `null`, or `{"removed_in": "4.0.0", "see": <issue URL>}` for a command that is scheduled for removal (every command under `slr`, and `report verify-latex`). It is on every node, so a group is marked as well as its leaves.

## Example
```bash
zotero-cli schema item trash | jq '.command | {path, effect, preview_by_default}'
```
```json
{ "path": ["item", "trash"], "effect": "write", "preview_by_default": true }
```

## Notes
*   Read-only: it changes nothing and needs no configuration or network.
*   The `effect` of every command is recorded in the source and a test fails when a new command isn't classified.
*   Stable: `schema_version` changes only if the layout of this document changes incompatibly.
