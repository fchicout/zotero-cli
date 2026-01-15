### 🎯 Objective
Warn users if a remote collection has changed during screening.

### 🔍 Technical Analysis
Uses checksums/hashes of collection versions in `TuiScreeningService`.

### 🛠 Proposed Solution
Implement a checksum validation that alerts the researcher if the collection count or versions change mid-session.

### ✅ Verification Plan
- [ ] **Unit Tests:** Detection logic verification.
- [ ] **Integration Tests:** Trigger warning in TUI mock.
- [ ] **Manual Check:** N/A

### 🔗 Traceability
- **Persona:** Gandalf
- **Phase:** Operations
