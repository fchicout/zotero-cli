# Command: `rag`

Retrieval-Augmented Generation (RAG) operations for Systematic Literature Reviews. This command promotes RAG to a top-level namespace for easier access to knowledge retrieval features.

## Verbs

### `ingest`
Ingests Zotero items (metadata and full-text) into the local vector database.

**Usage:**
```bash
zotero-cli rag ingest --collection "COLLECTION_NAME" [--approved] [--prune]
zotero-cli rag ingest --key "ITEMKEY"
zotero-cli rag ingest qa-approved --tree "raw_acm" [--qa-limit 0.7]
```

*   `--collection` / `--key`: what to ingest (a collection, or one item).
*   `--approved`: only items screened as included (`rsl:include`).
*   `--prune`: clear the vector store first (the default appends).
*   `qa-approved --tree SOURCE`: ingest the items that passed extraction QA in an SLR source tree.

### `query`
Queries the vector database using natural language.

**Usage:**
```bash
zotero-cli rag query "What are the key trends in LLM safety?" [--top-k 5] [--format json] [--ask]
```

*   The prompt is a positional argument.
*   `--ask` (alias `--synthesize`): also write an answer with the configured LLM.

### `context`
Retrieves synthesized context snippets for a specific item key.

**Usage:**
```bash
zotero-cli rag context --key "ITEMKEY"
```

### `purge`
Removes indexed data from the local vector store.

**Usage:**
```bash
zotero-cli rag purge --all
zotero-cli rag purge --key "ITEM_KEY"
zotero-cli rag purge --collection "COLLECTION_NAME/KEY"
```

### `model`
Manages RAG models (embeddings and generative).

**Usage:**
```bash
zotero-cli rag model set
zotero-cli rag model clean
```
