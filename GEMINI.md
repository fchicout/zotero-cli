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

## Project Overview: `zotero-cli`
A "Systematic Review Engine" CLI tool to import, manage, and screen research papers in Zotero libraries.

### Dual-Domain Architecture
1.  **The Engine (Management):** Direct manipulation of the Zotero database (items, collections, tags, storage).
2.  **The Protocol (SLR):** Advanced workflow support for Systematic Literature Reviews (Kitchenham/Wohlin).

## Rigid Feature Set (SLR Conformance)
| SLR Phase | CLI Implementation | Status |
| :--- | :--- | :--- |
| **Search & Collect** | `import arxiv`, `import file (RIS/BibTeX/CSV)` | [DONE] |
| **Title/Abstract Screening** | `slr screen` (TUI), `slr decide` (CLI), `slr load` | [DONE] |
| **Full-Text Screening** | `slr decide --phase full_text --evidence "..."` | [DONE] |
| **Data Extraction** | (Future scope: Structured JSON extraction forms) | [PLANNED] |
| **Synthesis & Reporting** | `report prisma`, `report snapshot`, `slr graph` | [DONE] |

**Key Technologies:** Python 3.10+, `requests`, `rich`, `pytest`.

## Accomplishments (Session: 2026-01-21)

### Phase 18: Semantic Consolidation & Full-Text (v2.2)
*   **[ARCH] Semantic CLI Consolidation (Issue #38, #40):** Unified all scientific/review commands under the `slr` namespace. Legacy aliases (`review`, `analyze`, `audit`) were purged after a deprecation cycle.
*   **[FEAT] Pre-flight Environment Checks (Issue #46):** Implemented "Boot Guard" pattern to enforce Python 3.10+ and handle dependency failures gracefully at the entry point.
*   **[FEAT] SLR Protocol Refinement (Issue #48):** Flattened the `slr` subcommand tree for better ergonomics (`slr load`, `slr validate`).
*   **[FEAT] SDB v1.2 & Phase Isolation (Issue #49, #50):** Added support for `full_text` screening phase with `evidence` capture. Notes are now isolated by persona AND phase to prevent data loss.
*   **[QUALITY] Valerius Review:** Synchronized the entire test suite (Unit/E2E) with the new CLI structure. Resolved pre-existing type safety violations in `slr_service.py`.
*   **[DOCS] Documentation Rewrite:** Completely updated `docs/commands/slr.md` and `USER_GUIDE.md` to reflect the new flat tree.

## Current State

*   **Version:** `v2.2.0-rc1`
*   **Quality:** 100% Core/CLI Unit Test Pass. 100% E2E Pass.
*   **Status:** **STABILIZATION v2.2**

## Next Actions (Immediate)
1.  **Infrastructure:** Implement Issue #30 (`--offline` mode).
2.  **Workflow:** Implement Issue #29 (`move` checkout/check-in).
3.  **Refactoring:** Refactor API `GET /items` to use native Zotero pagination.