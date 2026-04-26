import hashlib
import json
import logging
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

@dataclass
class VerificationReport:
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    manifest: Optional[dict] = None
    file_count: int = 0
    item_count: int = 0
    collection_count: int = 0

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
                file_list = zf.namelist()

                # 1. Verify Manifest
                if "manifest.json" not in file_list:
                    report.is_valid = False
                    report.errors.append("Missing manifest.json")
                else:
                    try:
                        manifest_content = zf.read("manifest.json").decode("utf-8")
                        report.manifest = json.loads(manifest_content)
                    except Exception as e:
                        report.is_valid = False
                        report.errors.append(f"Invalid manifest.json: {str(e)}")

                # 2. Verify Data
                if "data.json" not in file_list:
                    report.is_valid = False
                    report.errors.append("Missing data.json")
                else:
                    try:
                        data_content = zf.read("data.json").decode("utf-8")
                        items = json.loads(data_content)
                        report.item_count = len(items)
                    except Exception as e:
                        report.is_valid = False
                        report.errors.append(f"Invalid data.json: {str(e)}")

                # 3. Verify Collections (Optional for collection scope, required for library scope)
                if report.manifest and report.manifest.get("scope_type") == "library":
                    if "collections.json" not in file_list:
                        report.is_valid = False
                        report.errors.append("Missing collections.json for library-scoped backup")
                    else:
                        try:
                            coll_content = zf.read("collections.json").decode("utf-8")
                            colls = json.loads(coll_content)
                            report.collection_count = len(colls)
                        except Exception as e:
                            report.is_valid = False
                            report.errors.append(f"Invalid collections.json: {str(e)}")

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
                            report.errors.append(f"File {path} listed in manifest but missing from archive")
                            continue

                        if expected_checksum:
                            actual_checksum = self._calculate_checksum(zf, path)
                            if actual_checksum != expected_checksum:
                                report.is_valid = False
                                report.errors.append(f"Checksum mismatch for {path}: expected {expected_checksum}, got {actual_checksum}")

        except Exception as e:
            report.is_valid = False
            report.errors.append(f"Critical error during verification: {str(e)}")

        return report

    def _calculate_checksum(self, zf: zipfile.ZipFile, path: str) -> str:
        sha256_hash = hashlib.sha256()
        with zf.open(path) as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
