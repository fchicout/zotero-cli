# System Restore & ZAF Integrity Specification v1.0

**Status:** 🟡 DRAFT -> 🟢 APPROVED
**Architect:** Hamilton (Council)
**Date:** 2026-04-25

## 1. Executive Summary
This specification outlines the architectural blueprint for completing the "Full Featured Export and Import" capabilities of the `zotero-cli`. It addresses GitHub Issues #100 and #102, focusing on a flawless reverse-operation for `system restore` from a `.zaf` archive, ensuring ZAF integrity for cloud deletion trustworthiness, and supporting standard bibliographic formats for the `item inspect` command.

## 2. Technical Requirements

### [SPEC-ZAF-001] ZAF Integrity and Verification
- **Objective:** Ensure `.zaf` archives are complete and mathematically verifiable before any destructive actions (like cloud deletion) occur.
- **Implementation:**
  - Update `BackupService._process_item_recursive` to calculate SHA-256 (or MD5) checksums for all downloaded attachments and include them in `manifest.json` under `file_map` (e.g., `{"file_path": "attachments/key/file.pdf", "checksum": "..."}`).
  - Create a new command: `zotero-cli system verify --file <archive.zaf>` which reads the archive, validates all checksums of attachments against the manifest, and verifies the JSON structure of `data.json` and `collections.json`.

### [SPEC-ZAF-002] Flawless System Restore
- **Objective:** Implement the `zotero-cli system restore` command as a perfect reverse operation to `system backup`.
- **Implementation:**
  - Implement a new `RestoreService` in `src/zotero_cli/core/services/restore_service.py`.
  - **Idempotency:** During restoration, query the target library for existing items using DOI, Title, or ArXiv ID to prevent duplicates.
  - **Hierarchy Reconstruction:** Rebuild the collection tree using `collections.json`, maintaining a mapping of `old_collection_key -> new_collection_key`.
  - **Item Recreation:** Create items, replacing `old_collection_key` references with `new_collection_key` references. Keep a mapping of `old_item_key -> new_item_key`.
  - **Attachment Re-linking:** Iterate over `manifest.json`'s `file_map`. Extract the attachment from the `.zaf` ZIP and use `gateway.upload_attachment` to attach it to the `new_item_key`.
  - **Transactional Integrity:** Maintain a detailed log of successful vs. failed restorations. Support `--dry-run` to preview the restoration plan (e.g., "Will create 5 collections and 120 items").

### [SPEC-EXP-001] Bibliographic Export via Inspect
- **Objective:** Address Issue #100 by supporting `--format bibtex|ris` for `item inspect`.
- **Implementation:**
  - Update `InspectCommand` in `src/zotero_cli/cli/commands/item_cmd.py` to accept the `--format` argument.
  - When `--format` is specified, bypass the default human-readable panel.
  - Instantiate the `ExportService` and map the `ZoteroItem` to a `ResearchPaper`.
  - Utilize the existing `BibtexGateway` or `RisGateway` to serialize the item and print it directly to `stdout`.

## 3. Implementation Plan (Dev Squad)
1. **Phase 1: Verification & Checksums**
   - Update `BackupService` to include checksums.
   - Implement `system verify` command and `VerifyService` logic.
2. **Phase 2: Restore Command**
   - Implement `RestoreService` mapping logic and API interactions.
   - Connect `RestoreService` to `SystemCommand._handle_restore` with dry-run support.
3. **Phase 3: Inspect Export**
   - Update `InspectCommand` for `--format bibtex/ris` outputting to `stdout`.

## 4. Testing Requirements (QA Force)
- **Unit Tests:** Mock `ZoteroGateway` to test `RestoreService`'s duplicate detection and key mapping logic.
- **Integration Tests:** Generate a dummy `.zaf` archive, restore it to a clean mock group, and verify the resulting state matches the original exactly. Ensure `--dry-run` produces no mutations.
- **Coverage:** Maintain 100% test pass rate and >80% coverage for the new `RestoreService` and `VerifyService`.
