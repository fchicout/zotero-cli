### 🎯 Objective
Implement AI-assisted screening suggestions using local LLMs.

### 🔍 Technical Analysis
New service `SuggestService` in `core/services/` and command `analyze suggest`.

### 🛠 Proposed Solution
Implement `analyze suggest` using local LLMs (Ollama/Llama.cpp) to rank papers against protocol criteria.

### ✅ Verification Plan
- [ ] **Unit Tests:** Mock LLM responses.
- [ ] **Integration Tests:** CLI scenario verification.
- [ ] **Manual Check:** Verify suggestion quality against known samples.

### 🔗 Traceability
- **Persona:** Dr. Silas
- **Phase:** Intelligence
