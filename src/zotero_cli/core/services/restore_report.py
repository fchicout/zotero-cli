"""What a restore reports: its counts, errors and warnings, and its key map (Issue #721),
which says what became of every item, collection and saved search of the archive. Zotero gives
a new key to whatever a restore creates, so anything that refers to the library by key needs
the map to follow it. A leaf module: the restore service and the command line both use it."""

from __future__ import annotations

import json
import os
import secrets
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from zotero_cli.core.exceptions import UsageError
from zotero_cli.core.models import LibraryRef

FORMAT = "zotero-cli-key-map"
FORMAT_VERSION = 1

CREATED = "created"
EXISTING = "existing"
NOT_RESTORED = "not_restored"


class KeyOutcome(TypedDict, total=False):
    key: Optional[str]  # the key in the library now; None when it was not restored
    status: str  # created, existing or not_restored
    item_type: str  # items only


@dataclass
class RestoreReport:
    collections_created: int = 0
    items_created: int = 0
    items_skipped_existing: int = 0
    attachments_uploaded: int = 0
    attachments_skipped_existing: int = 0
    items_trashed: int = 0  # of the items created, how many went into the trash (Issue #683)
    relations_restored: int = 0  # related-item links rewritten to the new keys (Issue #686)
    searches_created: int = 0  # saved searches (Issue #678)
    searches_skipped_existing: int = 0
    errors: List[str] = field(default_factory=list)
    # Things the archive holds that this restore does not bring back, and why: not failures
    # of the restore itself (those are `errors`), but the user should know.
    warnings: List[str] = field(default_factory=list)
    is_dry_run: bool = False
    # What became of everything in the archive, by its key there (Issue #721): the key it has
    # in the library now and whether it was created, already there or not restored. Empty for
    # a dry run, which creates nothing.
    item_keys: Dict[str, KeyOutcome] = field(default_factory=dict)
    collection_keys: Dict[str, KeyOutcome] = field(default_factory=dict)
    search_keys: Dict[str, KeyOutcome] = field(default_factory=dict)
    source_library: Optional[LibraryRef] = None
    target_library: Optional[LibraryRef] = None


def created_key_outcome(key: str) -> KeyOutcome:
    return {"key": key, "status": CREATED}


def existing_key_outcome(key: str) -> KeyOutcome:
    return {"key": key, "status": EXISTING}


def complete_outcomes(
    archived: List[dict], outcomes: Dict[str, KeyOutcome], items: bool = False
) -> Dict[str, KeyOutcome]:
    """One entry for everything the archive holds: what the restore recorded, and
    `not_restored` for the rest, so nothing is missing from the map without saying so."""
    complete: Dict[str, KeyOutcome] = {}
    for raw in archived:
        if not isinstance(raw, dict) or "key" not in raw:
            continue
        outcome: KeyOutcome = {**outcomes.get(raw["key"], {"key": None, "status": NOT_RESTORED})}
        if items:
            outcome["item_type"] = str(raw.get("data", {}).get("itemType", ""))
        complete[raw["key"]] = outcome
    return complete


def _library(library: Optional[LibraryRef]) -> Optional[Dict[str, str]]:
    return None if library is None else {"type": library.type, "id": str(library.id)}


def key_map_document(report: RestoreReport, generator: str) -> Dict[str, Any]:
    return {
        "format": FORMAT,
        "version": FORMAT_VERSION,
        "generator": generator,
        # false when the restore reported errors: some of the not_restored may be failures
        "complete": not report.errors,
        "source_library": _library(report.source_library),
        "target_library": _library(report.target_library),
        "items": report.item_keys,
        "collections": report.collection_keys,
        "searches": report.search_keys,
    }


def check_key_map_path(path: str, archive: str) -> None:
    """Refuses, before anything is restored, a path the key map could not be written to."""
    target = Path(path)
    if target.is_dir():
        raise UsageError(f"--key-map: {path} is a directory.")
    if target.exists() and Path(archive).exists() and os.path.samefile(target, archive):
        raise UsageError("--key-map must not be the archive being restored.")
    folder = target.parent
    if not folder.is_dir():
        raise UsageError(f"--key-map: the directory {folder} does not exist.")
    if not os.access(folder, os.W_OK):
        raise UsageError(f"--key-map: the directory {folder} is not writable.")


def write_key_map(path: str, document: Dict[str, Any]) -> None:
    """Written beside the target and moved into place, so a half-written map never exists."""
    target = os.path.abspath(path)
    part = os.path.join(
        os.path.dirname(target), f".{os.path.basename(target)}.{secrets.token_hex(8)}.part"
    )
    # created like any new file (the user's umask decides its permissions)
    Path(part).touch(exist_ok=False)
    try:
        with open(part, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        if os.path.exists(target):  # a replaced file keeps its permissions
            os.chmod(part, stat.S_IMODE(os.stat(target).st_mode))
        os.replace(part, target)
    finally:
        if os.path.exists(part):
            os.remove(part)
