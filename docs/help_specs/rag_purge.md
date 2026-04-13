# Command: `rag purge`

Removes indexed data from the local vector store.

## Description
Clears specific or all indexed data from the local vector database to manage storage and ensure data freshness.

## Usage
```bash
zotero-cli rag purge --all
zotero-cli rag purge --key "ITEM_KEY"
zotero-cli rag purge --collection "COLLECTION_NAME/KEY"
```

## Options
* `--all`: Clear the entire vector_chunks table.
* `--key <ITEM_KEY>`: Clear chunks for a specific item.
* `--collection <COLLECTION_NAME/KEY>`: Clear chunks for all items in a collection.

## Cognitive Safeguards
* **Verification**: After a purge, a subsequent rag query should return no results for the affected items.
* **Resilience**: The operation does not fail if no chunks exist for a given key.
* **Safety**: Purge operations are irreversible.
