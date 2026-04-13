# DOC-SPEC: slr verify

## 1. Classification
- **Level:** 🟢 READ-ONLY (Consistency Verification)
- **Target Audience:** Researcher / SLR Lead

## 2. Logic Flow (Visual Synthesis)
```mermaid
graph TD
    A[Start Verification] --> B{Verify Mode?}
    B -- Collection --> C[Fetch Metadata for All Items in Collection]
    B -- LaTeX --> D[Parse LaTeX File for Citations: \cite{...}]
    C --> E[Check for Missing Critical Fields: DOI, Abstract, Date]
    D --> F[Match Citation Keys against Zotero Library]
    E --> G[Generate Consistency Report Table]
    F --> G
    G --> H{Missing Items Found?}
    H -- Yes --> I[Optionally Export Missing Keys to File]
    H -- No --> J[End: Verification Success]
    I --> J
```

## 3. Synopsis
Unified tool for verifying the metadata completeness of a collection or ensuring that all citations in a LaTeX manuscript exist within your Zotero library.

## 4. Description (Instructional Architecture)
The `slr verify` command is the "Consistency Gate" for scientific publishing. It performs two distinct but related verification tasks:
1.  **Collection Metadata Audit:** Scans a specific Zotero collection and identifies items missing "Canonical Metadata" (DOI, Publication Date, or Abstract). This is crucial for ensuring your final included papers meet reporting standards.
2.  **LaTeX Citation Sync:** Parses your LaTeX source code for `\cite{...}` commands and verifies that every cited paper actually exists in your Zotero library (based on Citation Keys). This prevents "Broken Citations" in your final manuscript.

The command outputs a detailed table showing exactly which items or citations failed the check, allowing for surgical fixes before submission.

## 5. Parameter Matrix
| Flag | Type | Description | Ergonomic Note |
| :--- | :--- | :--- | :--- |
| `--collection` | String | Name or Key of the collection to audit. | Metadata completeness check. |
| `--latex` | Path | Local path to your LaTeX manuscript file (`.tex`). | Citation consistency check. |
| `--verbose`| Flag | Displays detailed processing logs for every item. | Optional. |
| `--export-missing`| Path | File path to save the keys of items missing metadata. | Useful for batch processing. |

## 6. Scenario-Based Examples (Cognitive Anchors)
### Scenario: Pre-submission check of a LaTeX paper
**Problem:** I'm finishing my paper and want to make sure I haven't cited any papers that are missing from my "Master Zotero Library."
**Action:** `zotero-cli slr verify --latex "main.tex"`
**Result:** The CLI lists 3 citation keys found in the `.tex` file that do not have matching entries in Zotero, highlighting potential bibliography errors.

## 7. Cognitive Safeguards
- **Common Failure Modes:** Attempting to verify a LaTeX file using citation keys that don't match the Zotero `extra` field or `CitationKey` metadata. 
- **Safety Tips:** Use `--collection` during the review phase to maintain metadata quality, and use `--latex` during the writing phase to prevent technical errors in your references.
