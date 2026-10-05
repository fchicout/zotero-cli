# DOC-SPEC: slr source

> **Deprecated:** this command is removed in zotero-cli 4.0.0. The systematic-review workflow is moving out of zotero-cli into applications built on it; it keeps working, with a warning, throughout 3.x, and notes it wrote in your library are not changed. See [#541](https://github.com/fchicout/zotero-cli/issues/541).

## 1. Classification
- **Level:** [🟡 MODIFICATION (Structure Ingestion) | 🟢 READ-ONLY (Inventory Lists)]
- **Target Audience:** Researchers / SLR Leads

## 2. Logic Flow (Visual Synthesis)
```mermaid
graph TD
    A["Start SLR Source Ops"] --> B{"Verb?"}
    B -- "init" --> C["Create raw_ parent and 4-phase sub-collections"]
    C --> D["Print Group library warnings"]
    D --> E["End: Structure Created"]
    B -- "add" --> F["Select format strategy (RIS/BibTeX/CSV)"]
    F --> G["Import records into raw_ parent collection"]
    G --> H["End: Items Ingested"]
    B -- "list" --> I["Scan all active raw_ collections"]
    I --> J["Compute counts & completeness metrics"]
    J --> K["End: Health Inventory Rendered"]
```

## 3. Synopsis
Manages collection infrastructure initialization, targeted search result imports, and active source pipelines inventories.

## 4. Description (Instructional Architecture)
The `slr source` subcommands manage search results ingestion:
- **`init`**: Automatically sets up the four phase folders (`01_title_abstract`, `02_full_text`, `03_quality_assessment`, `04_data_extraction`) inside a main `raw_` collection.
- **`add`**: Imports search result files (RIS/BibTeX/CSV) directly into the `raw_` collection, automatically identifying formats (IEEE, Springer, etc.).
- **`list`**: Reviews the health and completion metrics of all raw ingestion pipelines.

## 5. Parameter Matrix
| Flag / Parameter | Type | Description | Ergonomic Note |
| :--- | :--- | :--- | :--- |
| `--file` | String | Path to RIS, BibTeX, or CSV file to import | Required. |
| `--collection` | String | Name or key of the raw collection (e.g. acm); `slr source add` only | Required for `add`. |
| `--name` | String | Source name (`slr source init`); for `add`, a deprecated alias of `--collection` | Required for `init`. Deprecated on `add`: removed in 4.0 (Issue #379). |
| `--details` | Boolean | Print verbose details | Optional. Default: False. |
| `--verbose` | Boolean | Deprecated alias of `--details` | Hidden; prints a warning. Removed in 4.0 (Issue #374). |

## 6. Scenario-Based Examples (Cognitive Anchors)
### Scenario: Initializing a new review pipeline for ACM papers
**Problem:** I need to prepare my Zotero collection hierarchy for upcoming ACM search result files.
**Action:** `zotero-cli slr source init --name "acm"`
**Result:** Creates `raw_acm` and its four nested phase directories.

## 7. Cognitive Safeguards
- **Common Failure Modes:** Attempting to `add` files into a collection name that does not exist or has not been initialized.
- **Safety Tips:** Always initialize your group library and target collection using `slr source init` before running `slr source add`.
