# Command: `serve`

Starts a local REST API server that exposes the Zotero library and internal CLI logic to external tools (like MCP servers or local scripts).

## Verbs

### `(default)`

Runs the FastAPI server.

**Usage:**
```bash
zotero-cli serve [--host HOST] [--port PORT] [--reload]
```

**Options:**
* `--host`: Bind host (default: 127.0.0.1).
* `--port`: Bind port (default: 1969).
* `--reload`: Enable auto-reload for development.

**Endpoints:**
* `GET /items`: List items with pagination and filtering.
* `GET /items/{key}`: Retrieve full item details.
* `GET /collections`: List collections hierarchy.
* `GET /health`: System status.
