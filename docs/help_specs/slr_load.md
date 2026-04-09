# DOC-SPEC: slr load

## 1. Classification
- **Level:** 🟡 MODIFICATION (Library Update)
- **Target Audience:** Researcher / Data Analyst

## 2. Logic Flow (Visual Synthesis)
```mermaid
graph TD
    A[Start Load] --> B[Read CSV]
    B --> C{Find Zotero Item?}
    C -- Matched by Key/DOI? --> D[Update Screening Notes]
    C -- Not Found? --> E[Skip / Log Unmatched]
    D --> F{Move Item?}
    F -- --move-to-included? --> G[Add to 'Included' Collection]
    F -- --move-to-excluded? --> H[Add to 'Excluded' Collection]
    G --> I[End: Status Updated]
    H --> I
```

## 3. Synopsis
Bulk-imports screening decisions from an external CSV file into your Zotero library, updating metadata and screening notes.

## 4. Description (Instructional Architecture)
The `slr load` command enables high-scale screening workflows. It allows you to use external tools (like Excel, Rayyan, or ASReview) for the actual screening and then "sync back" your decisions (INCLUDE/EXCLUDE, reasons, and evidence) to Zotero.

The command performs a **Matching Phase** (using Zotero Keys or DOIs) and an **Enrichment Phase** where it creates or updates Zotero Notes with the screening metadata (Reviewer, Phase, Vote, Reason, Evidence).

## 5. Parameter Matrix
| Flag | Type | Description | Ergonomic Note |
| :--- | :--- | :--- | :--- |
| `--file` | Path | Absolute or relative path to the CSV file. | Must contain at least a 'Key' or 'DOI' column. |
| `--reviewer` | String | Name or ID of the person who screened. | Used for audit tracking in Zotero notes. |
| `--phase` | String | SLR Phase (e.g., 'title_abstract'). | Default is 'title_abstract'. |
| `--force` | Switch | Apply changes to the library. | Always omit this first for a **Dry Run**. |
| `--move-to-included` | String | Target collection name. | Items with "INCLUDE" votes are moved here. |

## 6. Scenario-Based Examples (Cognitive Anchors)
### Scenario: Importing Rayyan Decisions
**Problem:** I screened 500 papers in Rayyan and exported a CSV. I need these decisions reflected in Zotero for my final audit.
**Action:** `zotero-cli slr load --file "rayyan_export.csv" --reviewer "Chicout" --phase "full_text" --move-to-included "Accepted" --force`
**Result:** 500 papers have their Zotero notes updated with "Chicout", "full_text", and "Accepted" status.

## 7. Cognitive Safeguards
- **Common Failure Modes:** CSV column headers not matching the default expectations ('Key', 'Vote', 'Reason'). Use `--col-key`, `--col-vote`, etc., to override mappings.
- **Safety Tips:** Always perform a dry run (omit `--force`) and review the results table for "Matched Items" before applying.
