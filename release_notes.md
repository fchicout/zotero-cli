# Release Notes - v2.7.0 (2026-05-07)

## 🚀 The "Cognitive Clarity" Release

This milestone focuses on repository professionalization, architectural refinement, and the introduction of a rigorous development protocol. We have sanitized the codebase, formalized requirements, and optimized the delivery pipeline for multi-platform distribution.

---

### 🛡️ Quality Assurance & Security Metrics
The release was finalized after passing the **High-Integrity Hexa-Gate**, ensuring a zero-defect baseline for both logic and security.

- **Test Pass Rate:** 100% (590 tests passed).
- **Code Coverage:** 78% (Core services and CLI entry points).
- **Security Audit (SAST):** Zero high-severity findings (Bandit & Safety).
- **Type Integrity:** 100% Success (Mypy strict check).
- **Complexity Guard:** All new functions maintain a cyclomatic complexity < 10 (Ruff C901).

---

### ✨ Major Enhancements & Refactoring

#### 📝 Strategic Documentation Suite
Established a formal documentation baseline in the `docs/` directory to improve architectural traceability and user onboarding:
- **`REQUIREMENTS.md`**: Detailed functional and non-functional mapping.
- **`USE_CASES.md`**: Documented primary user interactions and system flows.
- **`USER_STORIES.md`**: User-centric scenarios for researchers and authors.
- **`PROCESS.md`**: Formalized the "Golden Path v2.2" development protocol.

#### 🧹 Repository Hygiene & "Clean Root" Policy
- **Sanitized Root:** Misplaced data artifacts (`.csv`, `.json`, `.txt`) were relocated to the structured `data/` directory.
- **Cleanup:** Removed legacy coverage and temporary artifacts to ensure a focused workspace.

#### 🏗️ Architectural Improvements (SOLID/DRY/KISS)
- **SRP Refactoring:** Offloaded deep SDB filtering logic from `ItemCommand` to `SDBService`, centralizing metadata handling.
- **DRY Path Resolution:** Centralized project storage resolution in `get_storage_dir()` to eliminate OS-specific duplication across factories.
- **CI Optimization:** Optimized GitHub Actions to exclude heavy optional dependencies (`torch`, `nvidia`) from the distributed binaries, resolving 2GiB upload limits.

#### 🛠️ Security Hardening
- **Revision Pinning:** Implemented strict revision pinning for Hugging Face model downloads.
- **Dependency Upgrades:** Forced upgrades for `requests`, `pytest`, and `pygments` to resolve upstream vulnerabilities.
- **Input Sanitization:** Switched to `defusedxml` for secure XML parsing in bibliographic ingestion.

---
*Developed by the ARCH_MGMT Team (The Council)*
