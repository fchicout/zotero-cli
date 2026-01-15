### 🎯 Objective
Populate a local tracker from existing Zotero decision notes.

### 🔍 Technical Analysis
New `manage sync-csv` subcommand in `cli/commands/manage_cmd.py`.

### 🛠 Proposed Solution
Implement logic to scan child notes for JSON blocks and rebuild the local CSV state file.

### ✅ Verification Plan
- [ ] **Unit Tests:** Note parsing logic.
- [ ] **Integration Tests:** Rebuilds CSV from mocked Zotero library.
- [ ] **Manual Check:** Sync against test collection.

### 🔗 Traceability
- **Persona:** Sullivan
- **Phase:** Operations
