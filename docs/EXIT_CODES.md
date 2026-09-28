# Exit Codes

zotero-cli exits with one of these codes, so scripts and agents can tell what happened without parsing messages. Errors are printed as a single `Error: …` line on **stderr**; add `-v` to see the traceback. Every run also logs to the log file shown by `zotero-cli system info`.

| Code | Meaning | Examples |
| :--- | :--- | :--- |
| `0` | Success, including an empty result (`item list` or `search` that finds nothing) | |
| `1` | Error | a configuration problem, offline mode refusing a write, a file zotero-cli keeps its state in can't be read, an unexpected failure |
| `2` | Usage error | a missing or conflicting argument, a collection name that matches several collections, a confirmation needed but no terminal to ask on (pass `--force` / `--yes`) |
| `3` | Not found | a key, collection or file you named doesn't exist |
| `4` | Authentication | the API key was rejected or lacks access to the library |
| `5` | Unavailable | the network or the Zotero service failed after retries |
| `6` | Conflict | the object changed since the version the command acted on |
| `7` | Partial failure | part of a batch failed; the rest was applied |
| `130` | Interrupted | Ctrl-C |

Codes 3–7 are being rolled out command by command in the 3.0.x patch releases (Issue #368). Until that work is done, some failures still exit `1`, and exit codes are not yet part of the compatibility guarantees in [COMPATIBILITY.md](COMPATIBILITY.md).
