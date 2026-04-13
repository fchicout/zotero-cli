# DOC-SPEC: slr decide

## 1. Classification
- **Level:** 🟡 MODIFICATION (Single Item Audit)
- **Target Audience:** Researcher / Auditor

## 2. Logic Flow (Visual Synthesis)
```mermaid
graph TD
    A["Start Decide"] --> B["Fetch Item Key and Decision Details"]
    B --> C{"Vote?"}
    C -- "INCLUDE" --> D["Set Decision: accepted"]
    C -- "EXCLUDE" --> E["Set Decision: rejected + Exclusion Code"]
    D --> F["Prepare SDB Audit Note with Metadata"]
    E --> F
    F --> G["Execute API Request to Create/Update Note"]
    G --> H{"Source & Target Folders Set?"}
    H -- "Yes" --> I["Move Item from Source to Target"]
    H -- "No" --> J["Keep Item Position"]
    I --> K["End: Decision Recorded"]
    J --> K
```

## 3. Synopsis
Records a formal screening decision (Include/Exclude) for a single research item, ensuring a traceable audit trail by updating the item's internal Screening Database (SDB) notes.

## 4. Description (Instructional Architecture)
The `slr decide` command is the "Surgical Audit" tool for Systematic Literature Reviews. It allows you to record inclusion or exclusion results for individual items without entering the full `slr screen` TUI. 

This command is essential for maintaining scientific rigor. It not only records the binary decision but also captures the **Reviewer Persona**, the **Review Phase** (e.g., Title/Abstract, Full-Text), and the specific **Exclusion Code** or rationale. This metadata is stored as a persistent child note on the Zotero item, creating an immutable history of why every paper was chosen or rejected. 

## 5. Parameter Matrix
| Flag | Type | Description | Ergonomic Note |
| :--- | :--- | :--- | :--- |
| `--key` | String | Unique Zotero Item Key (e.g., `ABCD1234`). | Required. |
| `--vote`| Choice | `INCLUDE` or `EXCLUDE`. | Required. |
| `--code`| String | Exclusion criteria code (e.g., `E1`, `E2`). | Required for `EXCLUDE`. |
| `--phase`| String | The current review stage (e.g., `Title_Abstract`). | Recommended. |
| `--persona`| String | The name of the reviewer. | Recommended. |
| `--target` | String | Move item to this collection after decision. | Optional automation. |

## 6. Scenario-Based Examples (Cognitive Anchors)
### Scenario: Excluding a survey paper during review
**Problem:** I've identified that the paper with key `ABCD1234` is a survey, which violates my inclusion criteria (Code: `E2`).
**Action:** `zotero-cli slr decide --key "ABCD1234" --vote "EXCLUDE" --code "E2" --reason "Item is a survey paper"`
**Result:** The paper is marked as rejected in its internal audit note, citing criterion `E2`.

## 7. Cognitive Safeguards
- **Common Failure Modes:** Attempting to run `EXCLUDE` without providing a `--code`. The command will fail to ensure that no rejected paper lacks a justification. 
- **Safety Tips:** Use short, consistent codes (like `E1`, `E2`) for exclusion criteria to facilitate easier PRISMA reporting later via `report prisma`.
