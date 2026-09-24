# Command: `serve`

Starts a local REST API server that exposes the Zotero library and internal CLI logic to external tools (like MCP servers or local scripts).

## Verbs

### `(default)`

Runs the FastAPI server.

**Usage:**
```bash
zotero-cli serve [--host HOST] [--port PORT] [--reload] [--allow-remote] [--allowed-host HOST]
```

**Options:**
* `--host`: Bind host (default: 127.0.0.1).
* `--port`: Bind port (default: 1969).
* `--reload`: Enable auto-reload for development.
* `--allow-remote`: Allow a non-loopback `--host`. The server prints a bearer token at startup, which every request must send as `Authorization: Bearer <token>`. Without this flag, a non-loopback `--host` is refused.
* `--allowed-host HOST`: Also accept this `Host` header value (repeatable). By default only `127.0.0.1`, `localhost` and `::1` are accepted, which blocks DNS-rebinding attacks from web pages.

**Endpoints:**
* `GET /items`: List items with pagination and filtering.
* `GET /items/{key}`: Retrieve full item details.
* `GET /collections`: List collections hierarchy.
* `GET /jobs`, `GET /jobs/{id}`: Background job status.
* `GET /health`: System status.
