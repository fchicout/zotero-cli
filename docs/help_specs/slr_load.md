# DOC-SPEC: slr load

## 1. Classification
- **Level:** 🟡 MODIFICATION (Bulk Audit Update)
- **Target Audience:** Researcher / SLR Lead

## 2. Logic Flow (Visual Synthesis)
```mermaid
graph TD
    A["Start Load"] --> B["Parse Input CSV File"]
    B --> C["Match CSV Rows to Zotero Items via Key/DOI"]
    C --> D["Validate Column Mappings: Vote, Code, Reason"]
    D --> E{"Force Flag?"}
    E -- "No" --> F["Dry Run: Display Match Summary Table"]
    E -- "Yes" --> G["Bulk Execute API Note Updates"]
    G --> H{"Target Folders Set?"}
    H -- "Yes" --> I["Bulk Move Items to Include/Exclude Folders"]
    H -- "No" --> J["End: Load Results Stats"]
    F --> J
    I --> J
```

## 3. Synopsis
Bulk-imports screening decisions from an external CSV file (e.g., from Rayyan or Excel) into your Zotero library, updating internal audit notes and optionally triaging items into folders.

## 4. Description (Instructional Architecture)
The `slr load` command is the "Integration Bridge" for large-scale review projects. It is common to perform initial screening in dedicated tools like Rayyan or even in shared spreadsheets. This command allows you to bring those external decisions back into Zotero to maintain a centralized, authoritative research database. 

It uses a flexible matching logic that attempts to link CSV rows to Zotero items using the unique `Key` or the `DOI`. You can customize the column mappings to match your specific CSV header names. By default, the command runs in **Dry Run** mode, showing you exactly which items were matched and what decisions will be recorded. The `--force` flag is required to actually commit these changes to Zotero.

## 5. Parameter Matrix
| Flag | Type | Description | Ergonomic Note |
| :--- | :--- | :--- | :--- |
| `--file` | Path | Local path to the source CSV file. | Required. |
| `--reviewer`| String | Reviewer name for the audit trail. | Required. |
| `--phase` | String | Review phase (e.g., `Full_Text`). | Optional. |
| `--force` | Flag | Commits changes to the Zotero API. | Omit for a safe Dry Run. |
| `--col-vote`| String | Name of the "Decision" column in your CSV. | Default: `Vote`. |
| `--col-code`| String | Name of the "Exclusion Code" column. | Default: `Code`. |

## 6. Scenario-Based Examples (Cognitive Anchors)
### Scenario: Importing Rayyan screening results
**Problem:** I've finished a collaborative screening in Rayyan and I want the results reflected in my Zotero "Primary Review" folder.
**Action:** `zotero-cli slr load --file "rayyan_results.csv" --reviewer "Team_A" --force --move-to-included "ACCEPTED"`
**Result:** 500 items are matched, their audit notes updated, and accepted items are moved to the `ACCEPTED` folder.

## 7. Cognitive Safeguards
- **Common Failure Modes:** CSV column headers that don't match the command's defaults. Always use the `--col-*` flags if your CSV uses different names (e.g., `--col-vote "Decision"`). 
- **Safety Tips:** ALWAYS run without `--force` first. Review the output table to ensure that items are being matched correctly (especially if relying on DOI matching).
