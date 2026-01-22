# Gemini Workspace Context

This document preserves the context, memory, and task history of the `zotero-cli` project development session.

## Persona & Guidelines
**Role:** Interactive CLI Agent specializing in Software Engineering.

**Lead Team: The Py-Council of Six (High-Quality Python Development)**
*   **Pythias** (Lead Architect): SOLID, Type-Safety, Pythonic Rigor.
*   **Valerius** (Quality): Test Pyramid, 80%+ Coverage, Zero-Failure.
*   **Argentis** (Config): SemVer 2.0.0, Repository Hygiene, Traceability.
*   **Gandalf** (Secure Runner): Hardened Environments, Dependency Security.
*   **Sullivan** (Docs): Cognitive Clarity, Mermaid Visualization.
*   **Vitruvius** (Process): Deterministic CI/CD, The Golden Path.

**Scientific Advisor:**
*   **Dr. Silas:** Research Methodology, Bibliographic Rigor, Kitchenham/Wohlin Standards.

**Modus Operandi:**
We follow **[The Argentis Protocol](@gem-ctx/knowledge/PATTERNS.md#pattern-the-argentis-protocol-code-hygiene--lifecycle)** for all repository operations.

**Quality Assurance:**
All development must strictly adhere to **[The Valerius Protocol](@gem-ctx/knowledge/PATTERNS.md#pattern-the-valerius-protocol-quality-gate)**.
- **Criteria:** 100% Pass / >80% Coverage / Zero Mypy Errors.

## Team Activation Protocol (Workflow Accelerators)
To switch context instantly, use these trigger phrases:

*   **"Bring the council on"** -> Loads `.team/ARCH_MGMT.md`
    *   *Action:* Reads Backlog & Architect Inbox.
*   **"Activate Dev Squad"** -> Loads `.team/DEV_SQUAD.md`
    *   *Action:* Reads Dev Inbox & Source Code.
*   **"Call the QA Force"** -> Loads `.team/QA_FORCE.md`
    *   *Action:* Reads QA Inbox & runs `pytest`.

## Project Overview: `zotero-cli`
A "Systematic Review Engine" CLI tool to import, manage, and screen research papers in Zotero libraries.

### Dual-Domain Architecture
1.  **The Engine (Management):** Direct manipulation of the Zotero database (items, collections, tags, storage).
2.  **The Protocol (SLR):** Advanced workflow support for Systematic Literature Reviews (Kitchenham/Wohlin).

## Rigid Feature Set (SLR Conformance)
(See [ROADMAP.md](ROADMAP.md) for execution state and release planning)

| SLR Phase | CLI Implementation | Status |
| :--- | :--- | :--- |
| **Search & Collect** | `import arxiv`, `import file (RIS/BibTeX/CSV)` | [DONE] |
| **Title/Abstract Screening** | `slr screen` (TUI), `slr decide` (CLI), `slr load` | [DONE] |
| **Full-Text Screening** | `slr decide --phase full_text --evidence "..."` | [DONE] |
| **Data Extraction** | `slr extract` (TUI + Export) | [DONE] |
| **Synthesis & Reporting** | `report prisma`, `report snapshot`, `slr graph` | [DONE] |

**Key Technologies:** Python 3.10+, `requests`, `rich`, `pytest`.

## Accomplishments (Session: 2026-01-22)

### Phase 21: Data Extraction Workflow (v2.3.0 Milestone)
*   **[QUALITY] CI/CD Rescue:** Fixed release blocker by creating `MANIFEST.in` and patching `release.yml` to bundle YAML templates in PyInstaller builds.
*   **[VERIFIED] Issue #42 (Schema Validator):** Validated `slr extract --init/--validate` logic.
*   **[VERIFIED] Issue #43 (Extraction TUI):** Implemented unit tests for `ExtractionTUI` and `OpenerService`. Resolved `ImportError` regressions in TUI test suite.
*   **[VERIFIED] Issue #44 (Synthesis Matrix):** Validated export logic for CSV, Markdown, and JSON formats. Reached **91% coverage** for `extraction_service.py`.
*   **[QUALITY] Hard Coverage Gate (80%):** Successfully expanded tests to maintain the 80% global coverage threshold after adding new features.

## Current State

*   **Version:** `v2.3.0`
*   **Quality:** 100% Pass Rate (296 tests). Global coverage: **80%**.
*   **Status:** **RELEASE READY (Stabilized)**

## Next Actions (Immediate)
1.  **Release:** Final push and tag `v2.3.0`.
2.  **Feature:** Implement Issue #39 (Snowballing Engine).
