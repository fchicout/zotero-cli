# Command: `mcp`

Lets AI clients read your Zotero library through the [Model Context Protocol](https://modelcontextprotocol.io). Needs the optional extra:

```bash
pip install 'zotero-command-line[mcp]'        # or: uv tool install 'zotero-command-line[mcp]'
```

The standalone binaries don't include it (like `rag`); install from PyPI.

## Verbs

### `serve`
Runs an MCP server on stdin/stdout. **Your AI client starts it** from its configuration; you don't run it by hand (stdout carries the protocol, so a terminal only shows that it starts and then waits).

**Usage:**
```bash
zotero-cli mcp serve
zotero-cli --offline mcp serve      # read the local zotero.sqlite; adds full-text search
```

**Client configuration** (the exact file depends on the client; Claude Desktop, Cursor and LM Studio take an `mcpServers` entry like this):
```json
{ "mcpServers": { "zotero": { "command": "zotero-cli", "args": ["--offline", "mcp", "serve"] } } }
```

**What it offers.** Nine tools, all read-only; nothing listens on a network port.

| Tool | What it does |
| :--- | :--- |
| `search_items` | Search by keyword or, with `fulltext` (needs `--offline`), inside the PDFs' text; filter by tags, type, collection, year, date added; sort and page. The same search as `zotero-cli search`. |
| `get_item` | One item in full: creators, date, DOI, abstract, tags, collection keys, attachments, note count. |
| `list_items` | The items of a collection, or of the library, paged. |
| `list_collections`, `list_tags` | The collections and the tags. |
| `get_annotations` | The highlights and notes made in an item's PDFs (as `item annotations`). |
| `get_item_text` | The text extracted from an item's PDF, capped (20,000 characters by default). |
| `get_bibliography` | Formatted references for item keys in a CSL style (as `--as bibliography`). |
| `describe_cli` | The `zotero-cli schema` document. |

Results are structured data. Lists are capped (at most 200 items), and every string has control characters removed and a length limit.

**Safety.**
*   **Read-only.** There are no write tools. A phase with writes (preview first, trash only) would be a separate, opt-in addition.
*   **Untrusted content.** Titles, abstracts, annotations and PDF text may have been written by other people, for example in a shared group library. The server tells the client to treat them as data and never as instructions, but only connect clients you trust with your library.
*   **Errors.** A wrong key or argument is reported with its message so the client can correct itself; unexpected failures show a generic message and the details stay in the log (`zotero-cli system info` shows where).
*   Needs a configured library (`zotero-cli init`) like any other command.
