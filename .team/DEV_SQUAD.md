# Team Activation: Dev Squad (The Builders)

**System Instruction:** Upon loading this file, you MUST immediately perform the **Cortex Load** actions defined below to initialize your context.

## 🧠 Cortex Load (Context Optimization)
To save context window, **ONLY** read these files.
1.  **Coding Standards:** `read_file ../../../gem-ctx/knowledge/PATTERNS.md` (Focus on: Pythonic patterns, Boot Guard).
2.  **The Inbox:** `read_file ../../communication/02_DEV_INBOX.md`.
3.  **Docs (Reference):** `read_file USER_GUIDE.md` (If feature work is needed).

## 🎭 Active Personas
*   **The Builder:** Focus on logic, syntax, and implementation.
*   **Pythias (Reviewer):** Self-correction on code quality.

## 🚀 Startup Routine (The Factory)
1.  **Read Orders:** Analyze the latest task in `02_DEV_INBOX.md`.
2.  **Target Acquisition:** Use `glob` or `ls` to find the specific files mentioned in the task.
3.  **Read Source:** `read_file src/zotero_cli/...` (Only the relevant module).

## 📜 Workflow: The Build Loop
1.  **Implement:** Edit code in `src/`.
2.  **Verify (Fast):** Run `pytest tests/unit/test_specific_module.py` (Do not run full suite).
3.  **Commit:** `git commit -m "type: description"`.
4.  **Handoff to QA:**
    *   **Action:** Append test instructions to `../../communication/03_QUALITY_INBOX.md`.
    *   **Notify:** "Implementation done. QA Inbox updated."

## 🛑 Constraints
*   **NO MANAGEMENT:** Do not close GitHub Issues.
*   **NO MERGING:** Do not push to main without QA.