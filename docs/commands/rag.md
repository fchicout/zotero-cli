# Command: `rag`

Retrieval-Augmented Generation (RAG) operations for Systematic Literature Reviews. This command promotes RAG to a top-level namespace for easier access to knowledge retrieval features.

## Verbs

### `ingest`
Ingests Zotero items (metadata and full-text) into the local vector database.

**Usage:**
```bash
zotero-cli rag ingest --collection "COLLECTION_NAME" [--all]
```

### `query`
Queries the vector database using natural language.

**Usage:**
```bash
zotero-cli rag query --prompt "What are the key trends in LLM safety?" [--top-k 5]
```

### `context`
Retrieves synthesized context snippets for a specific item key.

**Usage:**
```bash
zotero-cli rag context --key "ITEMKEY"
```
