"""
The format-version rule from docs/COMPATIBILITY.md (Issue #455): readers
accept every older version of a format zotero-cli writes, and refuse a newer
major version with a clear error instead of misreading it.
"""

from typing import Any, Optional

from zotero_cli.core.exceptions import DataFileError

# The highest major version of each format this release reads.
SUPPORTED_MAJOR = {
    "SDB note": 1,  # sdb_version / audit_version, currently 1.2
    "backup archive": 1,  # .zaf manifest "version", currently 1.1
    "snapshot": 1,  # slr report snapshot "schema_version", currently 1.0
}


def _major(version: Any) -> Optional[int]:
    try:
        return int(str(version).strip().split(".")[0])
    except (TypeError, ValueError):
        return None


def check_format_version(kind: str, version: Any, source: str) -> None:
    """Raises DataFileError when `version` of format `kind` is newer (by
    major) than this release reads, or isn't a version at all. A missing
    version is accepted: files from before versioning are the oldest kind."""
    if version is None:
        return
    major = _major(version)
    if major is None:
        raise DataFileError(f"{source}: unrecognised {kind} version {version!r}.")
    supported = SUPPORTED_MAJOR[kind]
    if major > supported:
        raise DataFileError(
            f"{source} was written by a newer zotero-cli ({kind} version {version}; this "
            f"release reads up to {supported}.x). Upgrade zotero-cli to use it; nothing was changed."
        )
