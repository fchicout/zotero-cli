# 📥 QUALITY_INBOX: System Restore & ZAF Integrity (Issues #100, #102 / Spec v1.0)

**Status:** 🟢 READY FOR IMPLEMENTATION
**Project:** zotero-cli
**Spec:** [docs/specs/SYSTEM_RESTORE_v1.0.md](../docs/specs/SYSTEM_RESTORE_v1.0.md)
**Priority:** High

## 🛠️ Task Description
Provide test coverage and execution audit for the new `system restore`, `system verify`, and `item inspect --format` features.

## 📋 Technical Requirements
1.  **Unit Tests:** Mock `ZoteroGateway` to test `RestoreService`'s duplicate detection, hierarchy reconstruction, and key mapping logic without hitting the live API.
2.  **Integration Tests:** Generate a dummy `.zaf` archive with checksums, restore it to a clean mock group, and verify the resulting state matches the original exactly.
3.  **Safety Verification:** Ensure `--dry-run` in `system restore` produces no mutations.

## 🛑 Critical Vetoes
- **VETO: The Coverage Breach:** Coverage < 80% is an automatic failure.
- **VETO: The Release Gamble:** Release requires 100% pass rate.

---
**Lead Persona:** Valerius (Quality Lead)
**Protocol:** Gatekeeper Loop
