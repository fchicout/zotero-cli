# DOC-SPEC: rag query

## 1. Classification
- **Level:** 🟢 READ-ONLY (Semantic Retrieval)
- **Target Audience:** Researcher / AI Analyst

## 2. Logic Flow (Visual Synthesis)

```mermaid
graph TD
    A["Start Query"] --> B["Generate Query Embedding"]
    B --> C["Search Vector DB"]
    C --> D["Retrieve Top-K Results"]
    D --> E["Hydrate with Zotero Metadata"]
    E --> F{"Output Format?"}
    F -- "Human" --> G[""Rich Table (Title, Authors, Snippet")"]
    F -- "Machine" --> H[""JSON (Full Data")"]
    G --> I["End: Display Results"]
    H --> I
```

## 3. Synopsis
Performs a semantic search across your indexed Zotero library to find the most relevant text snippets based on a natural language prompt.

## 4. Description (Instructional Architecture)
The `rag query` command allows you to interact with your library as a knowledge graph. Unlike traditional keyword search (grep), semantic search understands the context and intent behind your query. 

It works by converting your input string into a vector and finding the closest matches in the Vector Store (populated via `rag ingest`). Each result is "hydrated" with real-time metadata from the Zotero database, providing a complete picture that includes the source item's title, authors, and the specific text snippet that matched your query.

## 5. Parameter Matrix
| Flag | Type | Description | Ergonomic Note |
| :--- | :--- | :--- | :--- |
| `prompt` | String | The natural language search query. | Positional argument. Enclose in quotes if multi-word. |
| `--top-k` | Integer | Number of most relevant results to return. | Default: 5. |
| `--json` | Flag | Output results in raw JSON format for pipeline consumption. | Essential for integration with other AI tools. |

## 6. Scenario-Based Examples (Cognitive Anchors)
### Scenario: Finding implementation details across a library
**Problem:** I know I have papers that discuss "Layer Normalization" in Transformers, but I don't remember which ones or where in the text they describe it.
**Action:** `zotero-cli rag query "How is Layer Normalization applied in Transformer blocks?" --top-k 3`
**Result:** The CLI returns the 3 most relevant paragraphs from different papers, showing the exact text and the source citation.

## 7. Cognitive Safeguards
- **Common Failure Modes:** Running a query before ingesting any data. The search will return zero results if the vector store is empty.
- **Safety Tips:** Semantic search is probabilistic. High relevance scores (e.g., >0.85) indicate strong matches, but always verify the context in the original paper.
