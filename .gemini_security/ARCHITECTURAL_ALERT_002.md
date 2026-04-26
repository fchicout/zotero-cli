# ARCHITECTURAL ALERT: E2E Resource Leakage & Orphan Prevention
**Origin:** QA Force (Valerius)
**Date:** 2026-04-25

## 1. The Observation (Evidence)
- **File/Module:** `tests/e2e/`, `tests/e2e/conftest.py`
- **The "Stranger Thing":** 
    1. Multiple E2E tests (`test_collection_lifecycle`, `test_ops_e2e`) use manual `try/finally` blocks for resource cleanup.
    2. Audit (`test_resource_leak_audit.py`) discovered 6 leaked `E2E_Temp_` collections in the Zotero library, proving that manual cleanup is failing on test crashes or timeouts.
    3. The `temp_collection` fixture in `conftest.py` exists but is not used consistently across all E2E tests.

## 2. Risk Assessment
- **Valerius Protocol Violation:** Violation of the **Hierarchy-Aware Cleanup** mandate.
- **Impact:** Pollution of the Zotero Remote Library with "E2E_" garbage, leading to potential side effects in subsequent test runs and API rate limiting.

## 3. Proposed Reconciliation
- **Implement the Sentinel Pattern:** Introduce a `ResourceTracker` class in `conftest.py` as a global fixture.
- **Enforce Usage:** Refactor all E2E tests that create remote resources to use the `sentinel` fixture.
- **Automated Purge:** Add a session-start hook to purge any orphaned "E2E_" collections before running the suite.

---
**Directive:** The Council must authorize the transition from manual cleanup to the Sentinel pattern to ensure a clean state (Zero-Defect Handoff).
