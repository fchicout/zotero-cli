# Tutorial 03: Powering SLRs with Zotero CLI RAG

This guide explains how to transform your Zotero library into a semantically searchable knowledge base using the **Retrieval-Augmented Generation (RAG)** feature.

## 1. Prerequisites & Configuration
Before the **Engine** can process your research, ensure your environment matches the **ARCH_MGMT Council's** standards.

### Install PDF Support
The RAG system requires specialized libraries to extract text from academic papers.
```bash
pip install "markitdown[pdf]"
```

### Configure an AI Provider
Edit `~/.config/zotero-cli/config.toml` to include an API key for high-fidelity semantic search. The system supports both Google Gemini and OpenAI.

```toml
[zotero]
gemini_api_key = "your-gemini-api-key"  # Recommended for Council operations
# OR
openai_api_key = "your-openai-api-key"
```
*Note: If no key is provided, the system defaults to a `MockEmbeddingProvider` for testing purposes only (semantic search will not be accurate).*

---

## 2. Phase I: Knowledge Ingestion (`ingest`)
The `ingest` command acts as the **Librarian**, extracting full-text from PDF attachments and converting them into mathematical "embeddings" stored in a local SQLite vector database.

### Ingest a specific collection
```bash
zotero-cli rag ingest --collection "Deep Learning Papers"
```

### Ingest your entire library
```bash
zotero-cli rag ingest --all
```

---

## 3. Phase II: Semantic Discovery (`query`)
Unlike standard keyword search, RAG understands the **context** of your query. You can ask research questions directly to your library.

### Ask a research question
```bash
zotero-cli rag query "How do LLMs impact zero-day vulnerability detection?" --top-k 10
```
*   `--top-k`: Limits the output to the most relevant snippets found across all ingested documents.

---

## 4. Phase III: Context Extraction (`context`)
Once you identify an interesting paper via `query`, use the `context` command to dump the entire processed text of that item. This is ideal for feeding into other LLM agents or for deep reading.

### Extract full context for an item
```bash
zotero-cli rag context --key "ABC12345"
```

---

## 🛠️ Troubleshooting & Maintenance
*   **Missing Text:** Ensure your items have PDF attachments downloaded locally.
*   **Bad Gateway (502):** Usually a temporary Zotero API hiccup. Retry the command.
*   **Clear RAG Data:** Currently, the vector store is located at `~/.config/zotero-cli/vector_store.sqlite`. Deleting this file will reset all RAG data.
