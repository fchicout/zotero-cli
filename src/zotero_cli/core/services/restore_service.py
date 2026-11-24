import hashlib
import logging
import re
import zipfile
from dataclasses import dataclass, field
from typing import IO, Any, Dict, List, Optional, Set, Tuple, cast

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

_ITEM_URI = re.compile(r"^https?://zotero\.org/(users|groups)/(\d+)/items/([A-Za-z0-9]+)$")
_ANNOTATION = "annotation"  # itemType of a PDF highlight, note, ink or underline (Issue #685)


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
    items_trashed: int = 0  # of the items created, how many went into the trash (Issue #683)
    relations_restored: int = 0  # related-item links rewritten to the new keys (Issue #686)
    errors: List[str] = field(default_factory=list)
    # Things the archive holds that this restore does not bring back, and why: not failures
    # of the restore itself (those are `errors`), but the user should know.
    warnings: List[str] = field(default_factory=list)
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
        library: Optional[LibraryRef] = None,
    ):
        # The library being restored into (Issue #686): related-item links name it in their URI.
        self.library = library
        self._source: Optional[LibraryRef] = None  # the library the archive came from
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
        self._attachments_of: Dict[Tuple[str, bool, str], List[dict]] = {}
        # Stand-alone notes and files already in the library, as (text or md5, its collections),
        # taken from the one scan that also builds the DOI/title indexes (Issue #681).
        # The last part of each is "in the trash": the Web API hides trashed children from
        # their parent's listing, so the trash is scanned too (Issue #683).
        self._known_notes: Set[Tuple[str, Tuple[str, ...], bool]] = set()
        self._known_files: Dict[Tuple[Optional[str], Tuple[str, ...], bool], str] = {}
        self._trashed_children: Dict[str, List[ZoteroItem]] = {}
        self._trash_indexes: Tuple[Dict[str, ZoteroItem], Dict[str, ZoteroItem]] = ({}, {})
        self._trashed_note_texts: Dict[str, Set[str]] = {}

    def restore_archive(self, file_path: str, dry_run: bool = False) -> RestoreReport:
        report = RestoreReport(is_dry_run=dry_run)
        self._note_texts = {}
        self._created = set()
        self._attachments_of = {}
        self._known_notes = set()
        self._known_files = {}
        self._trashed_children = {}
        self._trash_indexes = ({}, {})
        self._trashed_note_texts = {}

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                # The archive may come from someone else: size-limited reads
                # (archive_safety) instead of zf.read() of whole entries.
                check_entry_count(zf)
                manifest = read_json_member(zf, "manifest.json")
                _check_manifest(manifest, file_path)
                self._source = LibraryRef.from_manifest(manifest.get("library"))
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

                # 3. Related items: only now do all the new keys exist (Issue #686)
                self._restore_relations(sorted_items, report)

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
        if item_type == _ANNOTATION:
            self._restore_annotation(item_raw, report)
            return

        # 1. Idempotency: Check by DOI, ArXiv ID, or Title
        existing_item = self._find_existing_item(data, doi_index, title_index)
        if existing_item is None and data.get("deleted"):
            existing_item = self._find_existing_item(data, *self._trash_indexes)
        if existing_item:
            self.item_map[old_key] = existing_item.key
            report.items_skipped_existing += 1
            return

        # 2. Prepare new item data
        new_data = data.copy()
        # `relations` name the old item keys; they are set again once every item exists (#686)
        for k in ["key", "version", "dateAdded", "dateModified", "relations"]:
            new_data.pop(k, None)

        old_colls = data.get("collections", [])
        new_colls = [self.coll_map.get(ck) for ck in old_colls if self.coll_map.get(ck)]
        new_data["collections"] = new_colls

        # 3. Create Item
        if report.is_dry_run:
            self.item_map[old_key] = f"DRY_RUN_{old_key}"
            self._created.add(self.item_map[old_key])
            report.items_created += 1
            report.items_trashed += 1 if data.get("deleted") else 0
        else:
            new_key = self.items.create_generic_item(new_data)
            if new_key:
                self.item_map[old_key] = new_key
                self._created.add(new_key)
                self._note_texts[new_key] = set()  # just created: no notes yet
                report.items_created += 1
                report.items_trashed += 1 if data.get("deleted") else 0
            else:
                report.errors.append(f"Failed to create item: {data.get('title', 'Unknown')}")

    def _restore_child_item(
        self, child_raw: dict, zf: zipfile.ZipFile, manifest: dict, report: RestoreReport
    ) -> None:
        data = child_raw.get("data", {})
        item_type = data.get("itemType")
        old_parent = data.get("parentItem")
        if old_parent is None:  # a note or file filed in a collection on its own (Issue #681)
            self._restore_standalone(child_raw, zf, manifest, report)
            return
        new_parent = self.item_map.get(old_parent)

        if not new_parent:
            why = (
                "images embedded in notes are not restored yet"
                if data.get("linkMode") == "embedded_image"
                else f"its parent {old_parent} was not restored"
            )
            report.warnings.append(_not_restored(child_raw, why))
            return

        if item_type == "note":
            self._restore_note(data, new_parent, report)
        elif item_type == "attachment":
            self._restore_attachment(child_raw, zf, manifest, new_parent, report)

    def _restore_standalone(
        self, child_raw: dict, zf: zipfile.ZipFile, manifest: dict, report: RestoreReport
    ) -> None:
        """A note or an attachment that has no parent: a top-level item, filed in the same
        collections as before (their keys mapped like an article's)."""
        data = child_raw.get("data", {})
        collections = [self.coll_map[k] for k in data.get("collections", []) if k in self.coll_map]
        if data.get("itemType") == "attachment":
            self._restore_attachment(child_raw, zf, manifest, None, report, collections)
            return
        text = data.get("note", "")
        trashed = bool(data.get("deleted"))
        if (text, tuple(sorted(collections)), trashed) in self._known_notes:
            report.items_skipped_existing += 1
        elif report.is_dry_run or self.items.create_generic_item(
            _note_payload(data, collections=collections)
        ):
            report.items_created += 1
            report.items_trashed += 1 if trashed else 0
        else:
            report.errors.append(
                f"Failed to create the stand-alone note: {_not_restored(child_raw, '')}"
            )

    def _restore_note(self, data: dict, new_parent: str, report: RestoreReport) -> None:
        note_content = data.get("note", "")
        if report.is_dry_run:
            return

        trashed = bool(data.get("deleted"))
        existing = self._existing_note_texts(new_parent, trashed)
        if note_content in existing:
            return

        if self.items.create_generic_item(_note_payload(data, parent=new_parent)):
            existing.add(note_content)
            report.items_trashed += 1 if trashed else 0

    def _existing_note_texts(self, parent: str, trashed: bool) -> Set[str]:
        """The texts of the notes `parent` has (Issue #440: asked once per parent), live ones
        from its children, trashed ones from the trash scan: the Web API hides a trashed
        child from its parent's listing (Issue #683)."""
        if trashed:
            if parent not in self._trashed_note_texts:
                self._trashed_note_texts[parent] = {
                    str(child.raw_data.get("data", {}).get("note"))
                    for child in self._trashed_children.get(parent, [])
                    if child.item_type == "note"
                }
            return self._trashed_note_texts[parent]
        existing = self._note_texts.get(parent)
        if existing is None:
            existing = {
                child.get("data", {}).get("note")
                for child in self.items.get_item_children(parent)
                if child.get("data", {}).get("itemType") == "note"
            }
            self._note_texts[parent] = existing
        return existing

    def _restore_attachment(
        self,
        child_raw: dict,
        zf: zipfile.ZipFile,
        manifest: dict,
        new_parent: Optional[str],
        report: RestoreReport,
        collections: Optional[List[str]] = None,
    ) -> None:
        data = child_raw.get("data", {})
        old_key = child_raw["key"]
        path_in_zip = self._attachment_member(child_raw, zf, manifest)
        if path_in_zip is None:
            if data.get("linkMode") in ("linked_url", "linked_file"):
                self._restore_link(child_raw, new_parent, report, collections)
            elif data.get("linkMode") in STORED_LINK_MODES:
                report.warnings.append(_not_restored(child_raw, "its file is not in the archive"))
            return

        existing_key = self._attached_key(new_parent, zf, path_in_zip, data, collections)
        if existing_key:
            self.item_map[old_key] = existing_key  # its annotations go under it (Issue #685)
            report.attachments_skipped_existing += 1
            return

        if report.is_dry_run:
            self._remember(old_key, f"DRY_RUN_{old_key}")
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
            item_data = _attachment_payload(data, collections if new_parent is None else None)
            new_key = self.attachments.upload_attachment_item(
                new_parent, temp_path, mime_type=mime_type, item_data=item_data
            )
            if new_key:
                self._remember(old_key, new_key)
                report.attachments_uploaded += 1
                report.items_trashed += 1 if data.get("deleted") else 0
            else:
                report.errors.append(f"Failed to upload attachment: {path_in_zip}")
        except Exception as e:
            report.errors.append(f"Failed to upload attachment {path_in_zip}: {str(e)}")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    def _remember(self, old_key: str, new_key: str) -> None:
        """An item this run made: its new key, and nothing to match its children against."""
        self.item_map[old_key] = new_key
        self._created.add(new_key)

    def _restore_link(
        self,
        child_raw: dict,
        new_parent: Optional[str],
        report: RestoreReport,
        collections: Optional[List[str]],
    ) -> None:
        """An attachment that is only a record, no file: a web link (`linked_url`) or a file on
        the user's own disk (`linked_file`, its path is kept). Created from its archived data."""
        data = child_raw.get("data", {})
        old_key = child_raw["key"]
        existing_key = self._link_key(new_parent, data, collections)
        if existing_key:
            self.item_map[old_key] = existing_key
            report.attachments_skipped_existing += 1
            return
        new_key = f"DRY_RUN_{old_key}"
        if not report.is_dry_run:
            payload = _attachment_payload(data, collections if new_parent is None else None)
            if new_parent:
                payload["parentItem"] = new_parent
            created = self.items.create_generic_item(payload)
            if not created:
                self._link_failed(child_raw, report)
                return
            new_key = created
        self._remember(old_key, new_key)
        report.items_created += 1
        report.items_trashed += 1 if data.get("deleted") else 0

    @staticmethod
    def _link_failed(child_raw: dict, report: RestoreReport) -> None:
        if child_raw.get("data", {}).get("linkMode") == "linked_file":
            # Checked against the Web API: "Linked files can only be added to user libraries".
            # Its record stays in the archive.
            why = "Zotero only accepts linked files in personal libraries"
            report.warnings.append(_not_restored(child_raw, why))
        else:
            report.errors.append(f"Failed to create the attachment: {_not_restored(child_raw, '')}")

    def _link_key(
        self, new_parent: Optional[str], data: dict, collections: Optional[List[str]]
    ) -> Optional[str]:
        """The key of the link record the library already has for this one, if any."""
        trashed = bool(data.get("deleted"))
        target = data.get("url") or data.get("path")
        if new_parent is None:
            return self._known_files.get((target, tuple(sorted(collections or [])), trashed))
        if new_parent in self._created:
            return None
        for existing in self._existing_children(new_parent, trashed, "attachment"):
            if (
                existing.get("linkMode") == data.get("linkMode")
                and (existing.get("url") or existing.get("path")) == target
            ):
                return str(existing["_key"])
        return None

    def _existing_children(self, parent: str, trashed: bool, item_type: str) -> List[dict]:
        """The `data` of the attachments (or annotations) an existing item has, each with its
        `_key`, asked once per parent (Issue #680); the trashed ones come from the trash scan,
        because the API hides a trashed child from its parent (#683)."""
        cache_key = (parent, trashed, item_type)
        if cache_key not in self._attachments_of:
            children = (
                [child.raw_data for child in self._trashed_children.get(parent, [])]
                if trashed
                else self.items.get_item_children(parent)
            )
            self._attachments_of[cache_key] = [
                {**child.get("data", {}), "_key": child.get("key")}
                for child in children
                if child.get("data", {}).get("itemType") == item_type
            ]
        return self._attachments_of[cache_key]

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

    def _attached_key(
        self,
        new_parent: Optional[str],
        zf: zipfile.ZipFile,
        path_in_zip: str,
        data: dict,
        collections: Optional[List[str]] = None,
    ) -> Optional[str]:
        """The key of the attachment the library already has for this file, if any (Issue #680):
        the same md5, or, for an attachment that has none, the same file name. An item this run
        created has nothing to match. A stand-alone file (no parent) is matched by md5 within
        the collections it is filed in (Issue #681)."""
        if new_parent is not None and new_parent in self._created:
            return None
        try:
            digest = _member_md5(zf, path_in_zip)
        except (ArchiveLimitError, OSError, KeyError):
            return None  # the upload reports the real problem
        trashed = bool(data.get("deleted"))
        if new_parent is None:
            where = tuple(sorted(collections or []))
            return self._known_files.get((digest, where, trashed))
        filename = data.get("filename")
        for other in self._existing_children(new_parent, trashed, "attachment"):
            if other.get("md5") == digest or (
                other.get("md5") is None and filename and other.get("filename") == filename
            ):
                return str(other["_key"])
        return None

    def _restore_relations(self, items: List[dict], report: RestoreReport) -> None:
        """Gives the items this run created their related-item links back, pointing at the new
        items (Issue #686). Both ends are stored on both items, so each side is rewritten."""
        for raw in items:
            relations = raw.get("data", {}).get("relations") or {}
            new_key = self.item_map.get(raw["key"])
            if not relations or not new_key or new_key not in self._created:
                continue
            mapped = self._map_relations(relations, raw, report)
            count = sum(len(uris) for uris in mapped.values())
            if not count:
                continue
            if report.is_dry_run or self.items.update_item(new_key, 0, {"relations": mapped}):
                report.relations_restored += count
            else:
                report.errors.append(
                    f"Failed to restore the related items of {_not_restored(raw, '')}"
                )

    def _map_relations(
        self, relations: dict, raw: dict, report: RestoreReport
    ) -> Dict[str, List[str]]:
        mapped: Dict[str, List[str]] = {}
        for predicate, targets in relations.items():
            for uri in [targets] if isinstance(targets, str) else targets:
                new_uri = self._new_uri(str(uri), raw, report)
                if new_uri:
                    mapped.setdefault(predicate, []).append(new_uri)
        return mapped

    def _new_uri(self, uri: str, raw: dict, report: RestoreReport) -> Optional[str]:
        """The link to the restored item, the same link when it is not one of ours (another
        library's item, or no item at all), or None when it names an item of the archive's
        library that the archive does not hold: it is dropped and said, never pointed at a
        wrong item."""
        match = _ITEM_URI.match(uri)
        if not match:
            return uri
        scope, library_id, old_key = match.groups()
        library_type = "user" if scope == "users" else "group"
        if self._source is not None and not self._source.same_as(
            LibraryRef(library_type, library_id)
        ):
            return uri  # an item of another library: nothing of ours
        new_key = self.item_map.get(old_key)
        if not new_key:
            if self._source is None:
                return uri  # an archive that does not say where it is from: cannot tell
            report.warnings.append(
                _not_restored(raw, f"related item {old_key} is not in the archive, link dropped")
            )
            return None
        if self.library is None:
            return _ITEM_URI.sub(lambda m: f"http://zotero.org/{m[1]}/{m[2]}/items/{new_key}", uri)
        scope = "users" if self.library.type == "user" else "groups"
        return f"http://zotero.org/{scope}/{self.library.id}/items/{new_key}"

    def _restore_annotation(self, raw: dict, report: RestoreReport) -> None:
        """A highlight, note, ink or underline of a PDF (Issue #685): a child of the PDF
        attachment, so it goes under that attachment's *new* key."""
        data = raw.get("data", {})
        parent = self.item_map.get(data.get("parentItem"))
        if not parent:
            report.warnings.append(_not_restored(raw, "its PDF was not restored"))
            return
        trashed = bool(data.get("deleted"))
        if self._annotation_exists(parent, data, trashed):
            report.items_skipped_existing += 1
        elif report.is_dry_run or self.items.create_generic_item(_annotation_payload(data, parent)):
            report.items_created += 1
            report.items_trashed += 1 if trashed else 0
        else:
            report.errors.append(f"Failed to create the annotation: {_not_restored(raw, '')}")

    def _annotation_exists(self, parent: str, data: dict, trashed: bool) -> bool:
        if parent in self._created:
            return False
        fields = ("annotationType", "annotationPosition", "annotationText", "annotationComment")
        return any(
            all(other.get(f) == data.get(f) for f in fields)
            for other in self._existing_children(parent, trashed, _ANNOTATION)
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
            self._note_standalone(item, False)
            _index_item(item, doi_index, title_index)
        trash_doi: Dict[str, ZoteroItem] = {}
        trash_title: Dict[str, ZoteroItem] = {}
        for item in self.items.get_trash_items():
            self._note_standalone(item, True)
            if item.parent_item:
                self._trashed_children.setdefault(item.parent_item, []).append(item)
            else:
                _index_item(item, trash_doi, trash_title)
        self._trash_indexes = (trash_doi, trash_title)
        return doi_index, title_index

    def _note_standalone(self, item: ZoteroItem, trashed: bool) -> None:
        """Remembers the stand-alone notes and files already in the library (Issue #681)."""
        if item.parent_item:
            return
        data = item.raw_data.get("data", {})
        where = tuple(sorted(item.collections))
        if item.item_type == "note":
            self._known_notes.add((data.get("note", ""), where, trashed))
        elif item.item_type == "attachment":
            identity = data.get("md5") or data.get("url") or data.get("path")
            self._known_files[(identity, where, trashed)] = item.key

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
        """Parents first, then their notes and attachments, then the annotations of the PDFs
        (grandchildren, Issue #685): each needs the new key of the one before."""
        parents, children, annotations = [], [], []
        for i in items:
            item_type = i.get("data", {}).get("itemType")
            if item_type in ["attachment", "note"]:
                children.append(i)
            elif item_type == _ANNOTATION:
                annotations.append(i)
            else:
                parents.append(i)
        return parents + children + annotations


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


def _not_restored(raw: dict, why: str) -> str:
    """`<type> "<title or start of the note>" (<key>): <why>`, for the restore report."""
    data = raw.get("data", {})
    text = data.get("title") or data.get("filename") or str(data.get("note", ""))[:40]
    label = f'{data.get("itemType", "item")} "{text}" ({raw.get("key", "?")})'
    return f"{label}: {why}" if why else label


def _note_payload(
    data: dict, parent: Optional[str] = None, collections: Optional[List[str]] = None
) -> dict:
    """A note created from what the archive holds about it (Issue #682): its text and its tags,
    with their types, under the new parent or in the mapped collections. `create_note` only
    ever sent the text."""
    payload: dict = {"itemType": "note", "note": data.get("note", ""), "tags": data.get("tags", [])}
    if parent:
        payload["parentItem"] = parent
    if collections is not None:
        payload["collections"] = collections
    if data.get("deleted"):
        payload["deleted"] = 1  # the Web API honours it on create (checked on a test library)
    return payload


def _index_item(
    item: ZoteroItem, doi_index: Dict[str, ZoteroItem], title_index: Dict[str, ZoteroItem]
) -> None:
    """Files `item` by its normalised DOI and its lower-cased title; the first one wins."""
    if item.doi:
        normalized = normalize_doi(item.doi)
        if normalized and normalized not in doi_index:
            doi_index[normalized] = item
    if item.title:
        title_index.setdefault(item.title.lower(), item)


# What an archived attachment has that a new one must not carry over: its identity and
# bookkeeping (the dates are #687, the relations #686).
_ATTACHMENT_LOCAL = {
    "key",
    "version",
    "dateAdded",
    "dateModified",
    "parentItem",
    "collections",
    "relations",
    "md5",
    "mtime",
    "deleted",
}


def _attachment_payload(data: dict, collections: Optional[List[str]] = None) -> Dict[str, Any]:
    """An attachment created from what the archive holds about it (Issue #684): title, file name,
    content type, link mode (`imported_file` or `imported_url`), url, access date, tags. The
    upload used to name everything after its temporary file."""
    payload = {k: v for k, v in data.items() if k not in _ATTACHMENT_LOCAL}
    payload.setdefault("title", "")  # never the upload's default, the temporary file's name
    if collections is not None:
        payload["collections"] = collections
    if data.get("deleted"):
        payload["deleted"] = 1
    return payload


def _annotation_payload(data: dict, parent: str) -> Dict[str, Any]:
    """An annotation created from what the archive holds about it, under the restored PDF
    (Issue #685): type, text, comment, colour, page label, sort index, position and tags (the
    real API takes all of these as they were archived, checked on a test library)."""
    payload = {k: v for k, v in data.items() if k not in _ATTACHMENT_LOCAL}
    payload["parentItem"] = parent
    if data.get("deleted"):
        payload["deleted"] = 1
    return payload
