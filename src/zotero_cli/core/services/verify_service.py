import logging
import zipfile
from dataclasses import dataclass, field
from typing import List, Optional

from zotero_cli.core.utils.archive_safety import check_entry_count, read_json_member
from zotero_cli.core.utils.checksum import sha256_stream

logger = logging.getLogger(__name__)

# The members of a .zaf this service reads.
_MANIFEST_FILE = "manifest.json"
_DATA_FILE = "data.json"
_COLLECTIONS_FILE = "collections.json"
_ERRORS_FILE = "errors.log"


@dataclass
class VerificationReport:
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    manifest: Optional[dict] = None
    file_count: int = 0
    item_count: int = 0
    collection_count: int = 0
    # What the archive's own errors.log says (Issue #656): the archive can be intact and
    # still lack items or files the backup could not save.
    logged_errors: int = 0
    logged_skipped: int = 0


class VerifyService:
    """
    Validates the integrity of .zaf (Zotero Archive Format) files.
    Checks manifest consistency, file checksums, and JSON structure.
    """

    def verify_archive(self, file_path: str) -> VerificationReport:
        report = VerificationReport()

        try:
            if not zipfile.is_zipfile(file_path):
                report.is_valid = False
                report.errors.append("File is not a valid ZIP archive")
                return report

            with zipfile.ZipFile(file_path, "r") as zf:
                check_entry_count(zf)
                file_list = zf.namelist()

                # 1. Verify Manifest
                if _MANIFEST_FILE not in file_list:
                    report.is_valid = False
                    report.errors.append("Missing manifest.json")
                else:
                    try:
                        report.manifest = read_json_member(zf, _MANIFEST_FILE)
                        from zotero_cli.core.services.restore_service import _check_manifest

                        _check_manifest(report.manifest, file_path)
                    except Exception as e:
                        report.is_valid = False
                        report.errors.append(f"Invalid manifest.json: {str(e)}")

                # 2. Verify Data
                if _DATA_FILE not in file_list:
                    report.is_valid = False
                    report.errors.append("Missing data.json")
                else:
                    try:
                        items = read_json_member(zf, _DATA_FILE)
                        report.item_count = len(items)
                    except Exception as e:
                        report.is_valid = False
                        report.errors.append(f"Invalid data.json: {str(e)}")

                if _ERRORS_FILE in file_list:
                    self._count_logged_problems(zf, report)

                # 3. Verify Collections: required for a library backup; a collection
                # backup has them from format 1.2 on (Issue #660), older ones do not.
                is_library = bool(
                    report.manifest and report.manifest.get("scope_type") == "library"
                )
                if is_library and _COLLECTIONS_FILE not in file_list:
                    report.is_valid = False
                    report.errors.append("Missing collections.json for library-scoped backup")
                elif _COLLECTIONS_FILE in file_list:
                    self._read_collections(zf, report)

                self._check_counts(report, file_list)

                # 4. Verify Files and Checksums
                if report.manifest and "file_map" in report.manifest:
                    file_map = report.manifest["file_map"]
                    report.file_count = len(file_map)

                    for item_key, file_info in file_map.items():
                        # Handle both old string format and new dict format for backward compatibility
                        if isinstance(file_info, str):
                            path = file_info
                            expected_checksum = None
                        else:
                            path = file_info.get("path")
                            expected_checksum = file_info.get("checksum")

                        if not path:
                            report.is_valid = False
                            report.errors.append(f"Missing path in manifest for item {item_key}")
                            continue

                        if path not in file_list:
                            report.is_valid = False
                            report.errors.append(
                                f"File {path} listed in manifest but missing from archive"
                            )
                            continue

                        if expected_checksum:
                            actual_checksum = self._calculate_checksum(zf, path)
                            if actual_checksum != expected_checksum:
                                report.is_valid = False
                                report.errors.append(
                                    f"Checksum mismatch for {path}: expected {expected_checksum}, got {actual_checksum}"
                                )

        except Exception as e:
            report.is_valid = False
            report.errors.append(f"Critical error during verification: {str(e)}")

        return report

    @staticmethod
    def _read_collections(zf: zipfile.ZipFile, report: VerificationReport) -> None:
        try:
            collections = read_json_member(zf, _COLLECTIONS_FILE)
        except Exception as e:
            report.is_valid = False
            report.errors.append(f"Invalid collections.json: {str(e)}")
            return
        report.collection_count = len(collections)
        root = (report.manifest or {}).get("root_collection_key")
        if root and root not in {c.get("key") for c in collections}:
            report.is_valid = False
            report.errors.append(f"collections.json does not contain the root collection {root}")

    @staticmethod
    def _check_counts(report: VerificationReport, file_list: List[str]) -> None:
        """Format 1.2 archives say how much they hold (Issue #659): a different number means
        the file was cut or edited. Older archives have no `counts`."""
        counts = (report.manifest or {}).get("counts")
        if not isinstance(counts, dict):
            return
        actual = {
            "items": report.item_count,
            "files": len((report.manifest or {}).get("file_map") or {}),
            "collections": report.collection_count if _COLLECTIONS_FILE in file_list else None,
        }
        for name, expected in counts.items():
            found = actual.get(name)
            if found is not None and found != expected:
                report.is_valid = False
                report.errors.append(
                    f"manifest counts {expected} {name}, the archive holds {found}"
                )

    @staticmethod
    def _count_logged_problems(zf: zipfile.ZipFile, report: VerificationReport) -> None:
        with zf.open(_ERRORS_FILE) as log:
            text = log.read(1_000_000).decode("utf-8", errors="replace")
        for line in text.splitlines():
            if line.startswith("SKIPPED: "):
                report.logged_skipped += 1
            elif line.strip():
                report.logged_errors += 1

    def _calculate_checksum(self, zf: zipfile.ZipFile, path: str) -> str:
        with zf.open(path) as f:
            return sha256_stream(f)
