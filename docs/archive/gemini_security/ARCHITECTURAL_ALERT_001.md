# ARCHITECTURAL ALERT: Zotero-CLI Interface & Test Fragility
**Origin:** QA Force (Valerius)
**Date:** 2026-04-25

## 1. The Observation (Evidence)
- **File/Module:** `zotero_cli.infra.sqlite_repo.SqliteZoteroGateway`, `zotero_cli.core.services.rag_service`
- **The "Stranger Things":**
    1. `SqliteZoteroGateway` fails to implement mandatory abstract methods (`update_items`, `update_note`, etc.), leading to `TypeError` during instantiation in multiple tests.
    2. `CitationService` and `RAGService` access `item.raw_data` directly instead of using domain model properties, causing brittle tests when `ZoteroItem` is mocked without full raw data.
    3. `RAGService.ingest` parameter mismatch between implementation (`item_keys`) and E2E test usage (`collection_key`).

## 2. Risk Assessment
- **DRY/SOLID Violation:** Violation of **Interface Segregation** and **Liskov Substitution Principle**. `SqliteZoteroGateway` claims to be a `ZoteroGateway` but is incomplete.
- **Impact:** High test failure rate (29 failed), blocked CI/CD, and high cognitive load for developers due to inconsistent interfaces.

## 3. Proposed Reconciliation
- **Fix Interface Gap:** Implement all missing abstract methods in `SqliteZoteroGateway` raising `ConfigurationError`.
- **Domain Model Decoupling:** Refactor services to prioritize `ZoteroItem` properties over `raw_data` whenever possible.
- **Test Alignment:** Update `test_rag_integration.py` to use `item_keys` via gateway resolution, matching the CLI logic.
- **CI Hardening:** Integrate `ruff` and `mypy` into GitHub Actions.

---
**Directive:** The Council must authorize these structural fixes to restore the Green State (Valerius Protocol).
