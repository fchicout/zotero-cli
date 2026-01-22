# Specification: SDB-Extraction v1.0

**Status:** DRAFT
**Related Issues:** #41, #42, #43, #44
**Author:** Pythias (The Council)

## 1. Objective
To define a standardized, machine-readable format for **Data Extraction** in Systematic Literature Reviews. This format must allow researchers to extract structured data (variables) from Zotero items and store them persistently within Zotero Notes, ensuring portability and offline capability.

## 2. The Definition Schema (`schema.yaml`)
Before extraction begins, the research team must define *what* they are looking for. This is controlled by a YAML configuration file.

### 2.1 Schema Structure
```yaml
title: "SLR Extraction Protocol 2026"
version: "1.0"
variables:
  - key: "study_design"          # unique identifier (snake_case)
    label: "Study Design"        # Human readable label
    type: "select"               # text, number, boolean, select, multi-select
    options:                     # Required for 'select' / 'multi-select'
      - "Case Study"
      - "Experiment"
      - "Survey"
      - "SLR"
    required: true
    description: "The primary methodology used."

  - key: "sample_size"
    label: "Sample Size"
    type: "number"
    required: false

  - key: "algorithm_used"
    label: "Algorithm"
    type: "text"
```

### 2.2 Supported Types
| Type | Python Type | Validation |
| :--- | :--- | :--- |
| `text` | `str` | Any string. |
| `number` | `float` / `int` | Must be numeric. |
| `boolean` | `bool` | `true` / `false`. |
| `select` | `str` | Must be one of `options`. |
| `multi-select` | `List[str]` | All items must be in `options`. |
| `date` | `str` (ISO8601) | YYYY-MM-DD format. |

---

## 3. The Data Schema (SDB Note Payload)
The actual extracted data is stored in a Zotero Note attached to the item.
It follows the **Standardized Decision Block (SDB)** pattern but with a `data_extraction` phase.

### 3.1 JSON Payload
```json
{
  "sdb_version": "1.2",
  "action": "data_extraction",
  "phase": "extraction",
  "persona": "researcher_name",
  "timestamp": "2026-01-22T14:30:00Z",
  "agent": "zotero-cli",
  "schema_version": "1.0", 
  "data": {
    "study_design": {
      "value": "Experiment",
      "evidence": "We conducted a controlled experiment with 50 participants...",
      "location": "p. 3, Section 2.1"
    },
    "sample_size": {
      "value": 50,
      "evidence": "Total of 50 participants.",
      "location": "p. 3"
    },
    "algorithm_used": {
      "value": "Random Forest",
      "evidence": null,
      "location": null
    }
  }
}
```

### 3.2 Field Definitions
- **`data`**: Dictionary where keys correspond to `schema.yaml` variable keys.
- **`value`**: The extracted answer. Type depends on the variable definition.
- **`evidence`**: (Optional) A direct quote from the text supporting the value.
- **`location`**: (Optional) Page number or section identifier.

---

## 4. Workflow Integration (SLR Namespace)

1.  **Init:** User runs `zotero-cli slr extract --init` to generate a template `schema.yaml`.
2.  **Define:** User edits `schema.yaml` to define their variables.
3.  **Validate:** User runs `zotero-cli slr extract --validate` to check YAML syntax.
4.  **Extract:**
    - User runs `zotero-cli slr extract [ITEM_KEY]`.
    - TUI (Text User Interface) loads the schema.
    - TUI presents a form for each variable.
    - User inputs Value + Evidence.
5.  **Save:** Tool generates the JSON payload and saves it as a Note in Zotero.
6.  **Export:** `zotero-cli report synthesis` reads these notes and generates a Matrix (CSV/Markdown).

## 5. Storage Strategy
- **One Note per Persona:** To allow multiple reviewers to extract data independently (Double-Blind Extraction), each reviewer gets their own note.
- **Identification:** Notes are identified by searching for:
    - `"action": "data_extraction"`
    - `"persona": "<current_user>"`
