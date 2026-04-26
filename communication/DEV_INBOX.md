# 📥 DEV_INBOX: System Restore & ZAF Integrity (Issues #100, #102 / Spec v1.0)

**Status:** 🟢 READY FOR IMPLEMENTATION
**Project:** zotero-cli
**Spec:** [docs/specs/SYSTEM_RESTORE_v1.0.md](../docs/specs/SYSTEM_RESTORE_v1.0.md)
**Priority:** High

## 🛠️ Task Description
Implement the **System Restore** and **ZAF Verification** logic to enable trustworthy archiving and safe cloud data deletion, as well as bibliographic export support for `item inspect`.

## 📋 Technical Requirements
1.  **Phase 1: Verification & Checksums**
    - Update `BackupService` to include SHA-256 checksums in `manifest.json`.
    - Implement `system verify` command and `VerifyService` logic.
2.  **Phase 2: Restore Command**
    - Implement `RestoreService` mapping logic and API interactions in `src/zotero_cli/core/services/restore_service.py`.
    - Handle idempotency, hierarchy reconstruction, item recreation, and attachment re-linking.
    - Connect `RestoreService` to `SystemCommand._handle_restore` with `--dry-run` support.
3.  **Phase 3: Inspect Export**
    - Update `InspectCommand` in `src/zotero_cli/cli/commands/item_cmd.py` to support `--format bibtex/ris`.
    - Use `ExportService` to output to `stdout`.

## 🛑 Critical Vetoes
- **No duplicates:** Ensure `RestoreService` checks for existing items by DOI/Title/ArXiv ID before creation.
- **No data loss:** Ensure `--dry-run` performs absolutely zero mutations.

---
**Lead Persona:** Hamilton (Lead Engineer)
**Protocol:** Valerius Protocol (Verify-Expand-Verify)
