### 🎯 Objective
Eliminate duplication between Unpaywall, Semantic Scholar, and Crossref clients.

### 🔍 Technical Analysis
Affects `infra/` clients and `core/interfaces.py`.

### 🛠 Proposed Solution
Create a `BaseAPIClient` handling retries, headers, and rate limiting using `requests.Session`.

### ✅ Verification Plan
- [ ] **Unit Tests:** Targeted coverage for base client logic.
- [ ] **Integration Tests:** Verify metadata fetching for all providers.
- [ ] **Manual Check:** N/A

### 🔗 Traceability
- **Persona:** Pythias
- **Phase:** v1.2.x
