import json
import logging
import mimetypes
import os
import secrets
import stat
import tempfile
import zipfile
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any, Callable, Dict, List, Optional, Set

from zotero_cli.core.interfaces import AttachmentRepository, CollectionRepository, ItemRepository
from zotero_cli.core.models import LibraryRef
from zotero_cli.core.services.children_index import children_by_parent
from zotero_cli.core.utils.checksum import sha256_stream
from zotero_cli.core.utils.link_modes import STORED_LINK_MODES
from zotero_cli.core.zotero_item import ZoteroItem

logger = logging.getLogger(__name__)

# Prefixes of the lines of errors.log (Issue #656). A line without either, from an older
# archive, is a problem.
_SKIPPED = "SKIPPED: "
_LIBRARY = (
    "library"  # the scope of a whole-library backup, and the manifest entry naming the library
)
_ERROR = "ERROR: "
_INCLUDES_TRASH = "includes_trash"  # manifest entry: the archive also holds the trash (#662)


@dataclass
class BackupReport:
    """What a backup wrote, and what it could not (Issue #656)."""

    items: int = 0
    files: int = 0
    # Problems that make the archive incomplete: a file that failed to download, a child
    # item that could not be fetched.
    errors: List[str] = field(default_factory=list)
    # Expected gaps, not failures: a linked file lives on the user's own disk, which the
    # Web API cannot serve. Its record and path are in the archive.
    skipped: List[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.errors


class BackupService:
    """
    Handles creation of .zaf (Zotero Archive Format) backup files.
    Metadata is DEFLATE-compressed; attachments that are already compressed
    (PDFs, images, archives) are stored as they are (Issue #427: LZMA ran at
    about 2 MB/s for an 8% smaller archive). Readers accept either method,
    so older LZMA archives restore as before.
    Supports recursive attachment hydration and system-wide coverage.
    """

    def __init__(
        self,
        items: ItemRepository,
        collections: CollectionRepository,
        attachments: AttachmentRepository,
        library: Optional[LibraryRef] = None,
    ):
        self.items = items
        self.collections = collections
        self.attachments = attachments
        # Which library is being backed up (Issue #659); None when the caller cannot say.
        self.library = library
        self.version = "1.2"
        # Paths already used in the archive being written, casefolded (Issue #654).
        self._used_paths: Set[str] = set()

    def backup_collection(
        self,
        collection_key: str,
        output: str | IO[bytes],
        on_item_processed: Optional[Callable[[ZoteroItem], None]] = None,
        include_trash: bool = False,
    ) -> BackupReport:
        """
        Backs up a specific collection, its items, and their attachments to a .zaf file.
        With `include_trash`, the items of the collection (or below it) that are in
        Zotero's trash come too (Issue #662).
        """
        col = self.collections.get_collection(collection_key)
        if not col:
            raise ValueError(f"Collection {collection_key} not found")

        col_name = col.get("data", {}).get("name", "Unknown")
        # The collection and every collection below it (Issue #657): the Web API and the
        # local database list only the items filed directly in a collection.
        all_collections = self.collections.get_all_collections()
        keys = _collection_and_descendants(all_collections, collection_key)
        # Their records go into the archive (Issue #660), so a restore can rebuild the
        # sub-tree with its names and nesting.
        by_key = {c["key"]: c for c in all_collections}
        by_key.setdefault(collection_key, col)
        tree = [by_key[key] for key in keys if key in by_key]

        manifest = {
            "format": "zaf",
            "version": self.version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scope_type": "collection",
            "root_collection_key": collection_key,
            "root_collection_name": col_name,
            "collection_keys": keys,
            _INCLUDES_TRASH: include_trash,
            "generator": "zotero-cli",
            "file_map": {},
        }

        # Fetch items. Converting to list to allow length calculation for progress bars if needed.
        items: List[ZoteroItem] = []
        seen: Set[str] = set()
        for key in keys:
            for item in self.collections.get_items_in_collection(key, top_only=True):
                if item.key not in seen:  # filed in several of these collections: once
                    seen.add(item.key)
                    items.append(item)
        # Their children, fetched together (Issue #426)
        children = children_by_parent(self.items, [i.key for i in items if _has_children(i)])
        self._add_grandchildren(children)
        if include_trash:
            self._add_trash(items, children, set(keys))
        return self._write_zip(output, manifest, items, children, on_item_processed, tree)

    def backup_system(
        self,
        output: str | IO[bytes],
        on_item_processed: Optional[Callable[[ZoteroItem], None]] = None,
        include_trash: bool = False,
    ) -> BackupReport:
        """
        Backs up the entire library, including all collections and orphan items. With
        `include_trash`, the items in Zotero's trash come too (Issue #662).
        """
        manifest = {
            "format": "zaf",
            "version": self.version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scope_type": _LIBRARY,
            _INCLUDES_TRASH: include_trash,
            "generator": "zotero-cli",
            "file_map": {},
        }

        items = list(self.items.get_all_items())
        # The library listing already contains every child in full: group
        # them locally instead of asking for each item's children and then
        # re-fetching each child (Issue #426: ~2.8 requests per item).
        children: Dict[str, List[Dict[str, Any]]] = {}
        for item in items:
            if item.parent_item:
                children.setdefault(item.parent_item, []).append(item.raw_data)
        if include_trash:
            self._add_trash(items, children, None)
        return self._write_zip(output, manifest, items, children, on_item_processed)

    def _describe_content(
        self,
        manifest: dict,
        items: List[ZoteroItem],
        collections: List[Dict[str, Any]],
        item_count: int,
    ) -> None:
        """What the archive says about itself (format 1.2, Issue #659): the library it comes
        from and how much it holds, so a restore can refuse a mismatch and `verify` can
        notice a truncated file."""
        library = self._library_entry(items, collections)
        if library:
            manifest[_LIBRARY] = library
        manifest["counts"] = {
            "items": item_count,
            "collections": len(collections),
            "files": len(manifest["file_map"]),
        }
        manifest.setdefault(_INCLUDES_TRASH, False)

    def _library_entry(
        self, items: List[ZoteroItem], collections: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """type and id from the gateway that was asked, the name from the `library` stub the
        Web API puts on every item and collection (the stub supplies the type and id too
        when the caller could not say)."""
        stubs = [i.raw_data.get(_LIBRARY) for i in items] + [c.get(_LIBRARY) for c in collections]
        stub = next((s for s in stubs if isinstance(s, dict) and s.get("id") is not None), {})
        library_type = self.library.type if self.library else stub.get("type")
        library_id = self.library.id if self.library else stub.get("id")
        if not library_type or library_id in (None, ""):
            return {}
        entry = {"type": str(library_type), "id": str(library_id)}
        if stub.get("name"):
            entry["name"] = str(stub["name"])
        return entry

    def _add_trash(
        self,
        items: List[ZoteroItem],
        children: Dict[str, List[Dict[str, Any]]],
        collection_keys: Optional[Set[str]],
    ) -> None:
        """Adds the trashed items (Issue #662), and the children of the trashed parents, which
        the trash listing may or may not contain. A collection backup (`collection_keys`) takes
        only the trashed items filed in those collections, and the trashed children of what it
        already holds."""
        trashed = list(self.items.get_trash_items())
        have = {i.key for i in items}
        if collection_keys is None:
            picked = {t.key for t in trashed if t.key not in have}
        else:
            picked = {
                t.key
                for t in trashed
                if not t.parent_item and t.key not in have and set(t.collections) & collection_keys
            }
            held = have | picked
            found = _trashed_children(trashed, held)
            while found:  # a trashed child, then an annotation of it, of something we hold
                picked |= found
                held |= found
                found = _trashed_children(trashed, held)
        chosen = [t for t in trashed if t.key in picked]
        parents = [t.key for t in chosen if not t.parent_item and _has_children(t)]
        fetched = children_by_parent(self.items, parents)
        self._add_grandchildren(fetched)
        for parent, kids in fetched.items():
            children.setdefault(parent, []).extend(kids)
        items.extend(chosen)

    def _add_grandchildren(self, children: Dict[str, List[Dict[str, Any]]]) -> None:
        """The annotations of the PDFs and the images embedded in notes are children of
        children (Issue #658): a library listing contains them, a collection's children
        lookup does not. One batched lookup per kind, whatever the number of PDFs."""
        kids = [child for group in children.values() for child in group]
        attachments = [c["key"] for c in kids if _raw_type(c) == "attachment"]
        notes = [c["key"] for c in kids if _raw_type(c) == "note"]
        children.update(children_by_parent(self.items, attachments, "annotation"))
        children.update(children_by_parent(self.items, notes, "attachment"))

    def _write_zip(
        self,
        output: str | IO[bytes],
        manifest: dict,
        items: List[ZoteroItem],
        children: Dict[str, List[Dict[str, Any]]],
        on_item_processed: Optional[Callable[[ZoteroItem], None]] = None,
        collections: Optional[List[Dict[str, Any]]] = None,
    ) -> BackupReport:
        if not isinstance(output, str):
            return self._write_archive(
                output, manifest, items, children, on_item_processed, collections
            )
        # Issue #653: a path is written to a temporary file next to it and moved over
        # the target only once the archive is complete, so a failed run (a dropped
        # connection, a full disk, Ctrl-C) leaves an earlier backup there untouched.
        target = os.path.abspath(output)
        part = os.path.join(
            os.path.dirname(target), f".{os.path.basename(target)}.{secrets.token_hex(8)}.part"
        )
        # Created like any new file (the user's umask decides its permissions)
        Path(part).touch(exist_ok=False)
        committed = False
        try:
            report = self._write_archive(
                part, manifest, items, children, on_item_processed, collections
            )
            if os.path.exists(target):  # a replaced file keeps its permissions
                os.chmod(part, stat.S_IMODE(os.stat(target).st_mode))
            os.replace(part, target)
            committed = True
            return report
        finally:
            if not committed and os.path.exists(part):
                os.remove(part)

    def _write_archive(
        self,
        output: str | IO[bytes],
        manifest: dict,
        items: List[ZoteroItem],
        children: Dict[str, List[Dict[str, Any]]],
        on_item_processed: Optional[Callable[[ZoteroItem], None]] = None,
        collections: Optional[List[Dict[str, Any]]] = None,
    ) -> BackupReport:
        errors: List[str] = []
        processed_keys: Set[str] = set()
        self._used_paths = set()
        # A collection backup brings its own sub-tree. A library backup lists every
        # collection, before any file is downloaded: a failure here costs nothing yet.
        if collections is None:
            collections = self.collections.get_all_collections()

        # data.json is written entry by entry to a temporary file and added
        # at the end, rather than built as one indented string in memory
        # (Issue #427: 8.2 s of a 12.9 s backup was that one writestr).
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_path = os.path.join(tmp_dir, "data.json")
            with (
                zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf,
                open(data_path, "w", encoding="utf-8") as data_file,
            ):
                writer = _JsonArrayWriter(data_file)
                for item in items:
                    if item.key in processed_keys:
                        continue

                    writer.add(item.raw_data)
                    processed_keys.add(item.key)

                    # Download attachment file if it's an attachment directly
                    self._download_attachment_file(item, zf, manifest, errors)

                    # Process children
                    self._process_children(
                        item,
                        children.get(item.key, []),
                        zf,
                        manifest,
                        errors,
                        writer,
                        processed_keys,
                        children,
                    )

                    # Notify progress
                    if on_item_processed:
                        on_item_processed(item)
                writer.close()
                data_file.close()

                # Write Manifest (including updated file_map)
                self._describe_content(manifest, items, collections, len(processed_keys))
                zf.writestr("manifest.json", json.dumps(manifest, indent=2))

                # Write Data
                zf.write(data_path, "data.json")

                # The collections: all of them for a library backup, the backed-up
                # collection and the ones below it for a collection backup (Issue #660)
                if collections or manifest["scope_type"] == _LIBRARY:
                    zf.writestr("collections.json", json.dumps(collections, separators=(",", ":")))

                # Write Errors if any
                if errors:
                    zf.writestr("errors.log", "\n".join(errors))

        return BackupReport(
            items=len(processed_keys),
            files=len(manifest["file_map"]),
            errors=[e for e in errors if not e.startswith(_SKIPPED)],
            skipped=[e for e in errors if e.startswith(_SKIPPED)],
        )

    def _free_path(self, directory: str, filename: str, key: str) -> str:
        """`directory/filename`, or, when that path is taken, `directory/<name>-<key><ext>`
        (Issue #654: one item can hold several attachments with the same file name, and
        stand-alone ones all share a directory). Compared case-insensitively, since the
        archive may be unpacked on Windows or macOS. Names that do not collide are unchanged."""
        path = f"{directory}/{filename}"
        stem, extension = os.path.splitext(filename)
        counter = 1
        while path.casefold() in self._used_paths:
            suffix = key if counter == 1 else f"{key}-{counter}"
            path = f"{directory}/{stem}-{suffix}{extension}"
            counter += 1
        return path

    def _download_attachment_file(
        self,
        item: ZoteroItem,
        zf: zipfile.ZipFile,
        manifest: dict,
        errors: List[str],
        parent_key: Optional[str] = None,
    ) -> None:
        """Downloads the physical attachment file, calculates its checksum, and registers it."""
        data = item.raw_data.get("data", {})
        if data.get("itemType") != "attachment" or data.get("linkMode") not in _FILE_LINK_MODES:
            return
        if item.key in manifest["file_map"]:
            return

        filename = _stored_filename(data, item.key)
        p_key = parent_key or data.get("parentItem") or "orphan"
        storage_path = self._free_path(f"attachments/{p_key}", filename, item.key)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tf:
                temp_path = tf.name

            if self.attachments.download_attachment(item.key, temp_path):
                zf.write(temp_path, storage_path, compress_type=_compression_for(data))

                # Calculate SHA-256 checksum [SPEC-ZAF-001]
                with open(temp_path, "rb") as f:
                    checksum = sha256_stream(f)

                self._used_paths.add(storage_path.casefold())
                manifest["file_map"][item.key] = {"path": storage_path, "checksum": checksum}
            elif data.get("linkMode") == "linked_file":
                errors.append(
                    f"{_SKIPPED}attachment {item.key} ({filename}) is a linked file on your own "
                    "computer, which the Web API cannot back up; its record and path are kept"
                )
            else:
                errors.append(f"{_ERROR}Failed to download attachment {item.key} ({filename})")
        except Exception as e:
            errors.append(f"{_ERROR}Error processing attachment {item.key}: {str(e)}")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    def _process_children(
        self,
        item: ZoteroItem,
        children: List[Dict[str, Any]],
        zf: zipfile.ZipFile,
        manifest: dict,
        errors: List[str],
        writer: "_JsonArrayWriter",
        processed_keys: Set[str],
        children_of: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        """
        Adds an item's children (attachments/notes) after it, and theirs in turn
        (annotations of a PDF, Issue #658). They come in full from the listing, so none
        is fetched again (Issue #426) unless only its key is known. `children_of` maps
        every parent key to its children.
        """
        if not _has_children(item):
            return

        for child_raw in children:
            child_key = child_raw.get("key")
            if not child_key or child_key in processed_keys:
                continue

            if "data" in child_raw:
                child: Optional[ZoteroItem] = ZoteroItem.from_raw_zotero_item(child_raw)
            else:
                # Only a key came back: fetch the item itself.
                child = self.items.get_item(child_key)
            if not child:
                errors.append(
                    f"{_ERROR}Could not fetch child item {child_key} for parent {item.key}"
                )
                continue
            writer.add(child.raw_data)
            processed_keys.add(child.key)

            # Download attachment file if the child is an attachment
            self._download_attachment_file(child, zf, manifest, errors, parent_key=item.key)

            # Its own children: annotations of a PDF, images embedded in a note
            self._process_children(
                child,
                children_of.get(child.key, []),
                zf,
                manifest,
                errors,
                writer,
                processed_keys,
                children_of,
            )


# Attachments whose file a backup tries to save (Issue #655). The first three are stored by
# Zotero and served by the Web API at items/<key>/file; a snapshot or a PDF the connector
# fetched from a URL is `imported_url`, an image pasted into a note is `embedded_image`.
# `linked_file` lives on the user's own disk, which the Web API cannot serve: it is tried
# so that the missing file is reported. `linked_url` is a link and has no file.
_FILE_LINK_MODES = (*STORED_LINK_MODES, "linked_file")


def _stored_filename(data: Dict[str, Any], key: str) -> str:
    """A safe file name for the archive: the attachment's own, else its title, else its key
    plus the extension its content type suggests. Never empty, so no attachment is skipped
    for lack of a name."""
    name = str(data.get("filename") or data.get("title") or "")
    safe = os.path.basename(name.replace("\\", "/"))
    if safe and safe not in (".", ".."):
        return safe
    content_type = str(data.get("contentType") or "").split(";")[0].strip()
    return key + (mimetypes.guess_extension(content_type) or "" if content_type else "")


def _collection_and_descendants(collections: List[Dict[str, Any]], root: str) -> List[str]:
    """`root` and the keys of every collection below it, parents before children. Each key
    is visited once, so a malformed parent loop cannot make this run forever."""
    children: Dict[str, List[str]] = {}
    for collection in collections:
        parent = collection.get("data", {}).get("parentCollection")
        if parent:
            children.setdefault(parent, []).append(collection["key"])
    found = [root]
    seen = {root}
    queue = deque(found)
    while queue:
        for child in children.get(queue.popleft(), []):
            if child not in seen:
                seen.add(child)
                found.append(child)
                queue.append(child)
    return found


def _trashed_children(trashed: List[ZoteroItem], held: Set[str]) -> Set[str]:
    """The keys of the trashed items whose parent is in `held` and that are not in it yet."""
    return {t.key for t in trashed if t.parent_item in held and t.key not in held}


def _raw_type(raw: Dict[str, Any]) -> Optional[str]:
    item_type = raw.get("data", raw).get("itemType")
    return item_type if isinstance(item_type, str) else None


def _has_children(item: ZoteroItem) -> bool:
    # Attachments have annotations, notes have embedded images (Issue #658); only an
    # annotation is a leaf.
    return item.item_type != "annotation"


# Content types that are already compressed: stored as they are.
_PRECOMPRESSED_PREFIXES = ("image/", "video/", "audio/")
_PRECOMPRESSED_TYPES = {
    "application/pdf",
    "application/zip",
    "application/gzip",
    "application/x-7z-compressed",
    "application/epub+zip",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _compression_for(data: Dict[str, Any]) -> int:
    content_type = str(data.get("contentType") or "").lower()
    if content_type in _PRECOMPRESSED_TYPES or content_type.startswith(_PRECOMPRESSED_PREFIXES):
        return zipfile.ZIP_STORED
    return zipfile.ZIP_DEFLATED


class _JsonArrayWriter:
    """Writes a JSON array to a file one element at a time (compact)."""

    def __init__(self, file: IO[str]):
        self.file = file
        self.count = 0
        file.write("[")

    def add(self, element: Any) -> None:
        if self.count:
            self.file.write(",")
        json.dump(element, self.file, separators=(",", ":"))
        self.count += 1

    def close(self) -> None:
        self.file.write("]")
