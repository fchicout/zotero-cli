# Tutorial 04: The RAG-Driven Writing Workflow (SLR Synthesis)

This document formalizes the **ARCH_MGMT Council's** strategy for using RAG to synthesize a Systematic Literature Review (SLR) narrative.

## 🏛️ Strategic Overview
A Systematic Review is only as good as its synthesis. The RAG feature allows you to query your **Included** set as a unified knowledge body, ensuring your narrative is backed by semantic evidence.

---

## Phase 1: The Introduction (The "Why" and the "Gap")
Per the **Kitchenham Protocol**, your introduction must explicitly justify the necessity of this SLR.

*   **Query for Motivation:** 
    `zotero-cli rag query "What are the primary drivers for moving from traditional ML to LLMs in threat detection?"`
    *   **Goal:** Synthesize the "Motivation" section.
*   **Query for Gaps (The SLR Justification):**
    `zotero-cli rag query "What are the documented limitations or unanswered questions in current LLM-security research?"`
    *   **Goal:** Form the "Problem Statement" and justify your Research Questions (RQs).

---

## Phase 2: Background & Related Work (The Taxonomy)
Let the RAG cluster concepts to save weeks of manual reading.

*   **Query for Categorization:**
    `zotero-cli rag query "How do existing studies categorize LLM applications (e.g., prompt engineering vs fine-tuning vs RAG)?"`
    *   **Goal:** Draft your **Background Taxonomy**.
*   **Deep Dive:** Use `zotero-cli rag context --key [PILLAR_PAPER]` on the 3 most significant papers to ensure accurate summarization of foundational works.

---

## Phase 3: Results & Discussion (The Synthesis)
Extract specific evidence across the entire set.

*   **Evidence Extraction:**
    `zotero-cli rag query "What specific datasets (e.g., CIC-IDS2017) are most commonly used to evaluate LLM performance?"`
    *   **Goal:** Build your "Data Sources" results table.
*   **Conflict Discovery:**
    `zotero-cli rag query "Are there conflicting reports on the latency vs accuracy trade-off in real-time threat detection?"`
    *   **Goal:** Provide the "Nuance" for your **Discussion** section.

---

## Phase 4: Conclusion & Future Work
*   **Future Work Synthesis:**
    `zotero-cli rag query "What do researchers suggest as the next immediate steps for making LLMs production-ready in SOCs?"`

---

## 🧭 Council Best Practices (Vitruvius & Dr. Silas)
1.  **Isolate Your Sets:** Ingest ONLY the `Included` collection when writing the results. This prevents "Noise" from rejected papers from polluting your synthesis.
2.  **Verify via Context:** If a snippet in a `query` result seems surprising, run `rag context --key [KEY]` to read the surrounding text and ensure the semantic meaning is correct.
3.  **Traceability:** Always keep a log of the queries you used to generate sections; this adds an extra layer of auditability to your research process.
