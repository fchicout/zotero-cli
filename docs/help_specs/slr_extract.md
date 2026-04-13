# DOC-SPEC: slr extract

## 1. Classification
- **Level:** 🟢 READ-ONLY (Data Extraction)
- **Target Audience:** Researcher / AI Analyst

## 2. Logic Flow (Visual Synthesis)
```mermaid
graph TD
    A["Start Extraction"] --> B{"Extraction Scope?"}
    B -- "Collection" --> C["Identify All Items in Collection"]
    B -- "Key" --> D["Identify Single Item Key"]
    C --> E["Fetch Item Fulltext and Metadata"]
    D --> E
    E --> F{"Agent Mode?"}
    F -- "Yes" --> G["Trigger AI Extraction of Research Variables"]
    F -- "No" --> H[""Wait for Human Input (If implemented")"]
    G --> I["Format Extraction Matrix: Sample Size, Method, Results"]
    H --> I
    I --> J{"Export to File?"}
    J -- "Yes" --> K["Write to JSON/BibTeX Archive"]
    J -- "No" --> L["Display in Terminal"]
    K --> M["End: Extraction Success"]
    L --> M
```

## 3. Synopsis
Systematically extracts research variables, methodologies, and quantitative results from the full text of research papers, optionally using AI agents.

## 4. Description (Instructional Architecture)
The `slr extract` command is the "Insight Layer" of the systematic review. Once papers have been screened and included, the next step is to extract the data needed for synthesis. 

This command scans the full text of papers (relying on previously ingested PDF data via `rag ingest`) and identifies key information such as:
- **Research Methodology** (e.g., Case Study, Experiment).
- **Sample Sizes** and participant demographics.
- **Key Findings** and quantitative metrics.
In `--agent` mode, the CLI leverages Large Language Models to perform this extraction autonomously, generating a structured "Extraction Matrix" that can be exported for final analysis.

## 5. Parameter Matrix
| Flag | Type | Description | Ergonomic Note |
| :--- | :--- | :--- | :--- |
| `--collection` | String | Name or Key of the folder to process. | Bulk extraction. |
| `--key` | String | Unique Zotero Item Key. | Single item extraction. |
| `--agent`  | Flag | Enables AI-driven automated extraction. | Requires RAG ingestion. |
| `--persona`| String | The AI persona used for extraction. | e.g., `MethodologyExpert`. |
| `--export` | Path | File path to save the extraction results. | Supports `.json`. |

## 6. Scenario-Based Examples (Cognitive Anchors)
### Scenario: Building a summary table of research methods
**Problem:** I have 30 included papers and I want to know the primary research method used in each without re-reading all of them.
**Action:** `zotero-cli slr extract --collection "INCLUDED_PAPERS" --agent --export "methods_matrix.json"`
**Result:** The CLI processes the papers and generates a JSON file summarizing the methodologies discovered by the AI agent.

## 7. Cognitive Safeguards
- **Common Failure Modes:** Attempting extraction on items that haven't been processed by `rag ingest`. The command requires the vector store to "see" the internal text of the PDFs. 
- **Safety Tips:** AI extraction is a heuristic process. Always manually verify a subset of the extracted data against the original papers to ensure the agent's accuracy.
