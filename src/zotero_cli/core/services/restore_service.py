import hashlib
import logging
import zipfile
from dataclasses import dataclass, field
from typing import IO, Dict, List, Optional, Set, Tuple, cast

from zotero_cli.core.interfaces import (
    AttachmentRepository,
    CollectionRepository,
    ItemRepository,
    NoteRepository,
)
from zotero_cli.core.models import LibraryRef
from zotero_cli.core.utils.archive_safety import (
    MAX_ATTACHMENT_BYTES,
    ArchiveLimitError,
    check_entry_count,
    copy_member,
    read_json_member,
)
from zotero_cli.core.utils.format_version import check_format_version
from zotero_cli.core.utils.link_modes import STORED_LINK_MODES
from zotero_cli.core.utils.normalization import normalize_doi
from zotero_cli.core.zotero_item import ZoteroItem


def _check_manifest(manifest: object, source: str) -> None:
    """Refuse an archive that isn't a .zaf or is from a newer format (#455)."""
    from zotero_cli.core.exceptions import DataFileError

    if not isinstance(manifest, dict) or manifest.get("format", "zaf") != "zaf":
        raise DataFileError(f"{source} is not a zotero-cli backup archive (.zaf).")
    check_format_version("backup archive", manifest.get("version"), source)


logger = logging.getLogger(__name__)


def archive_library(file_path: str) -> Optional[LibraryRef]:
    """The library a .zaf says it was taken from (format 1.2, Issue #659); None for an older
    archive, which does not say."""
    with zipfile.ZipFile(file_path, "r") as zf:
        manifest = read_json_member(zf, "manifest.json")
    _check_manifest(manifest, file_path)
    return LibraryRef.from_manifest(manifest.get("library"))


@dataclass
class RestoreReport:
    collections_created: int = 0
    items_created: int = 0
    items_skipped_existing: int = 0
    attachments_uploaded: int = 0
    attachments_skipped_existing: int = 0
    errors: List[str] = field(default_factory=list)
    is_dry_run: bool = False


class RestoreService:
    """
    Handles restoration of Zotero libraries and collections from .zaf archives.
    Implements idempotency, hierarchy reconstruction, and asset re-linking.
    """

    def __init__(
        self,
        items: ItemRepository,
        collections: CollectionRepository,
        notes: NoteRepository,
        attachments: AttachmentRepository,
    ):
        self.items = items
        self.collections = collections
        self.notes = notes
        self.attachments = attachments
        self.item_map: Dict[str, str] = {}  # old_key -> new_key
        self.coll_map: Dict[str, str] = {}  # old_key -> new_key
        # new parent key -> the note texts it has, fetched once per parent
        # (Issue #440: one children request per restored note)
        self._note_texts: Dict[str, Set[str]] = {}
        # Items this run created (their key; a placeholder in a dry run): nothing to match
        # their attachments against. Every other parent is an existing item, whose attachments
        # (md5, file name) are fetched once, so restoring twice does not upload twice (#680).
        self._created: Set[str] = set()
        self._attachments_of: Dict[str, List[Tuple[Optional[str], Optional[str]]]] = {}

    def restore_archive(self, file_path: str, dry_run: bool = False) -> RestoreReport:
        report = RestoreReport(is_dry_run=dry_run)
        self._note_texts = {}
        self._created = set()
        self._attachments_of = {}

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                # The archive may come from someone else: size-limited reads
                # (archive_safety) instead of zf.read() of whole entries.
                check_entry_count(zf)
                manifest = read_json_member(zf, "manifest.json")
                _check_manifest(manifest, file_path)
                items_data = read_json_member(zf, "data.json")

                collections_data = []
                if "collections.json" in zf.namelist():
                    collections_data = read_json_member(zf, "collections.json")

                # 1. Reconstruct Collections
                if collections_data:
                    self._restore_collections(collections_data, report)

                # 2. Restore Items (Top-level first, then children)
                sorted_items = self._sort_items_by_hierarchy(items_data)

                # One library-wide scan, indexed by DOI and title, reused for
                # every item's idempotency check below instead of two full
                # scans (get_items_by_doi + get_all_items) per item
                # (Issue #277, same class as #267).
                doi_index, title_index = self._build_existing_item_indexes()

                for item_raw in sorted_items:
                    self._restore_single_item(
                        item_raw, zf, manifest, report, doi_index, title_index
                    )

        except Exception as e:
            report.errors.append(f"Critical error during restore: {str(e)}")

        return report

    def _restore_collections(self, colls: List[dict], report: RestoreReport) -> None:
        def get_depth(c: dict, all_colls: List[dict]) -> int:
            parent = c.get("data", {}).get("parentCollection")
            if not parent:
                return 0
            parent_coll = next((pc for pc in all_colls if pc["key"] == parent), None)
            if not parent_coll:
                return 0
            return 1 + get_depth(parent_coll, all_colls)

        sorted_colls = sorted(colls, key=lambda c: get_depth(c, colls))

        # Fetched once for the whole loop, not per collection (Issue #277) -
        # this reflects the destination library's pre-existing collections;
        # collections created earlier in this same loop are tracked via
        # self.coll_map instead, so they don't need to appear here too.
        existing_cols = self.collections.get_all_collections()

        for c_raw in sorted_colls:
            old_key = c_raw["key"]
            name = c_raw["data"]["name"]
            old_parent = c_raw["data"].get("parentCollection")
            new_parent = self.coll_map.get(old_parent) if old_parent else None

            match = next(
                (
                    ec
                    for ec in existing_cols
                    if ec["data"]["name"] == name
                    # The Web API says `false` for "no parent": that is no parent, too
                    and (ec["data"].get("parentCollection") or None) == new_parent
                ),
                None,
            )

            if match:
                self.coll_map[old_key] = match["key"]
            else:
                if report.is_dry_run:
                    self.coll_map[old_key] = f"DRY_RUN_{old_key}"
                    report.collections_created += 1
                else:
                    new_key = self.collections.create_collection(name, parent_key=new_parent)
                    if new_key:
                        self.coll_map[old_key] = new_key
                        report.collections_created += 1
                    else:
                        report.errors.append(f"Failed to create collection: {name}")

    def _restore_single_item(
        self,
        item_raw: dict,
        zf: zipfile.ZipFile,
        manifest: dict,
        report: RestoreReport,
        doi_index: Dict[str, ZoteroItem],
        title_index: Dict[str, ZoteroItem],
    ) -> None:
        data = item_raw.get("data", {})
        item_type = data.get("itemType")
        old_key = item_raw["key"]

        if item_type in ["attachment", "note"]:
            self._restore_child_item(item_raw, zf, manifest, report)
            return

        # 1. Idempotency: Check by DOI, ArXiv ID, or Title
        existing_item = self._find_existing_item(data, doi_index, title_index)
        if existing_item:
            self.item_map[old_key] = existing_item.key
            report.items_skipped_existing += 1
            return

        # 2. Prepare new item data
        new_data = data.copy()
        for k in ["key", "version", "dateAdded", "dateModified"]:
            new_data.pop(k, None)

        old_colls = data.get("collections", [])
        new_colls = [self.coll_map.get(ck) for ck in old_colls if self.coll_map.get(ck)]
        new_data["collections"] = new_colls

        # 3. Create Item
        if report.is_dry_run:
            self.item_map[old_key] = f"DRY_RUN_{old_key}"
            self._created.add(self.item_map[old_key])
            report.items_created += 1
        else:
            new_key = self.items.create_generic_item(new_data)
            if new_key:
                self.item_map[old_key] = new_key
                self._created.add(new_key)
                self._note_texts[new_key] = set()  # just created: no notes yet
                report.items_created += 1
            else:
                report.errors.append(f"Failed to create item: {data.get('title', 'Unknown')}")

    def _restore_child_item(
        self, child_raw: dict, zf: zipfile.ZipFile, manifest: dict, report: RestoreReport
    ) -> None:
        data = child_raw.get("data", {})
        item_type = data.get("itemType")
        old_parent = data.get("parentItem")
        new_parent = self.item_map.get(old_parent)

        if not new_parent:
            return

        if item_type == "note":
            self._restore_note(data, new_parent, report)
        elif item_type == "attachment":
            self._restore_attachment(child_raw, zf, manifest, new_parent, report)

    def _restore_note(self, data: dict, new_parent: str, report: RestoreReport) -> None:
        note_content = data.get("note", "")
        if report.is_dry_run:
            return

        existing = self._note_texts.get(new_parent)
        if existing is None:
            existing = {
                child.get("data", {}).get("note")
                for child in self.items.get_item_children(new_parent)
                if child.get("data", {}).get("itemType") == "note"
            }
            self._note_texts[new_parent] = existing
        if note_content in existing:
            return

        if self.notes.create_note(new_parent, note_content):
            existing.add(note_content)

    def _restore_attachment(
        self,
        child_raw: dict,
        zf: zipfile.ZipFile,
        manifest: dict,
        new_parent: str,
        report: RestoreReport,
    ) -> None:
        data = child_raw.get("data", {})
        path_in_zip = self._attachment_member(child_raw, zf, manifest)
        if path_in_zip is None:
            return

        if self._already_attached(new_parent, zf, path_in_zip, data):
            report.attachments_skipped_existing += 1
            return

        if report.is_dry_run:
            report.attachments_uploaded += 1
            return

        import os
        import tempfile

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=os.path.splitext(path_in_zip)[1]
            ) as tf:
                temp_path = tf.name
                copy_member(zf, path_in_zip, tf, MAX_ATTACHMENT_BYTES)

            mime_type = str(data.get("contentType") or "application/pdf")
            if self.attachments.upload_attachment(new_parent, temp_path, mime_type=mime_type):
                report.attachments_uploaded += 1
            else:
                report.errors.append(f"Failed to upload attachment: {path_in_zip}")
        except Exception as e:
            report.errors.append(f"Failed to upload attachment {path_in_zip}: {str(e)}")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    @staticmethod
    def _attachment_member(child_raw: dict, zf: zipfile.ZipFile, manifest: dict) -> Optional[str]:
        """Where the archive keeps the attachment's file, or None when it has none to restore."""
        if child_raw.get("data", {}).get("linkMode") not in (*STORED_LINK_MODES, "linked_file"):
            return None
        file_info = manifest.get("file_map", {}).get(child_raw["key"])
        if not file_info:
            return None
        path_in_zip = file_info if isinstance(file_info, str) else file_info.get("path")
        return path_in_zip if path_in_zip and path_in_zip in zf.namelist() else None

    def _already_attached(
        self, new_parent: str, zf: zipfile.ZipFile, path_in_zip: str, data: dict
    ) -> bool:
        """Whether the existing item `new_parent` already has this file (Issue #680): the same
        md5, or, for an attachment that has none, the same file name. An item this run created
        has nothing to match."""
        if new_parent in self._created:
            return False
        if new_parent not in self._attachments_of:
            self._attachments_of[new_parent] = [
                (child["data"].get("md5"), child["data"].get("filename"))
                for child in self.items.get_item_children(new_parent)
                if child.get("data", {}).get("itemType") == "attachment"
            ]
        try:
            digest = _member_md5(zf, path_in_zip)
        except (ArchiveLimitError, OSError, KeyError):
            return False  # the upload reports the real problem
        filename = data.get("filename")
        return any(
            md5 == digest or (md5 is None and name is not None and name == filename)
            for md5, name in self._attachments_of[new_parent]
        )

    def _build_existing_item_indexes(
        self,
    ) -> Tuple[Dict[str, ZoteroItem], Dict[str, ZoteroItem]]:
        """
        One get_all_items() pass, indexed by normalized DOI and lowercased
        title, reused by every _find_existing_item() call instead of each
        item doing its own get_items_by_doi() scan plus (on a miss) its own
        get_all_items() scan - two full-library scans per item instead of
        one for the whole restore (Issue #277, same class as #267).
        """
        doi_index: Dict[str, ZoteroItem] = {}
        title_index: Dict[str, ZoteroItem] = {}
        for item in self.items.get_all_items():
            if item.doi:
                normalized = normalize_doi(item.doi)
                if normalized and normalized not in doi_index:
                    doi_index[normalized] = item
            if item.title:
                key = item.title.lower()
                if key not in title_index:
                    title_index[key] = item
        return doi_index, title_index

    def _find_existing_item(
        self,
        data: dict,
        doi_index: Dict[str, ZoteroItem],
        title_index: Dict[str, ZoteroItem],
    ) -> Optional[ZoteroItem]:
        doi = data.get("DOI")
        if doi:
            normalized = normalize_doi(doi)
            if normalized and normalized in doi_index:
                return doi_index[normalized]

        # Fallback to Title + Year matching for robustness [SPEC-ZAF-002-UPDATE]
        title = data.get("title")
        if title:
            # Simple exact title match as a baseline
            return title_index.get(title.lower())
        return None

    def _sort_items_by_hierarchy(self, items: List[dict]) -> List[dict]:
        parents = []
        children = []
        for i in items:
            if i.get("data", {}).get("itemType") in ["attachment", "note"]:
                children.append(i)
            else:
                parents.append(i)
        return parents + children


class _Md5Sink:
    """A write-only file that only hashes what it is given."""

    def __init__(self) -> None:
        self.md5 = hashlib.md5(usedforsecurity=False)

    def write(self, chunk: bytes) -> int:
        self.md5.update(chunk)
        return len(chunk)


def _member_md5(zf: zipfile.ZipFile, name: str) -> str:
    sink = _Md5Sink()
    copy_member(zf, name, cast(IO[bytes], sink), MAX_ATTACHMENT_BYTES)
    return sink.md5.hexdigest()
