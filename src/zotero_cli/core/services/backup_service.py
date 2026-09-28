import json
import logging
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from typing import IO, Any, Callable, Dict, List, Optional, Set

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.children_index import children_by_parent
from zotero_cli.core.zotero_item import ZoteroItem

logger = logging.getLogger(__name__)


class BackupService:
    """
    Handles creation of .zaf (Zotero Archive Format) backup files.
    Metadata is DEFLATE-compressed; attachments that are already compressed
    (PDFs, images, archives) are stored as they are (Issue #427: LZMA ran at
    about 2 MB/s for an 8% smaller archive). Readers accept either method,
    so older LZMA archives restore as before.
    Supports recursive attachment hydration and system-wide coverage.
    """

    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway
        self.version = "1.1"

    def backup_collection(
        self,
        collection_key: str,
        output: str | IO[bytes],
        on_item_processed: Optional[Callable[[ZoteroItem], None]] = None,
    ) -> None:
        """
        Backs up a specific collection, its items, and their attachments to a .zaf file.
        """
        col = self.gateway.get_collection(collection_key)
        if not col:
            raise ValueError(f"Collection {collection_key} not found")

        col_name = col.get("data", {}).get("name", "Unknown")

        manifest = {
            "format": "zaf",
            "version": self.version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scope_type": "collection",
            "root_collection_key": collection_key,
            "root_collection_name": col_name,
            "generator": "zotero-cli",
            "file_map": {},
        }

        # Fetch items. Converting to list to allow length calculation for progress bars if needed.
        items = list(self.gateway.get_items_in_collection(collection_key, top_only=True))
        # Their children, fetched together (Issue #426)
        children = children_by_parent(self.gateway, [i.key for i in items if _has_children(i)])
        self._write_zip(output, manifest, items, children, on_item_processed)

    def backup_system(
        self,
        output: str | IO[bytes],
        on_item_processed: Optional[Callable[[ZoteroItem], None]] = None,
    ) -> None:
        """
        Backs up the entire library, including all collections and orphan items.
        """
        manifest = {
            "format": "zaf",
            "version": self.version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scope_type": "library",
            "generator": "zotero-cli",
            "file_map": {},
        }

        items = list(self.gateway.get_all_items())
        # The library listing already contains every child in full: group
        # them locally instead of asking for each item's children and then
        # re-fetching each child (Issue #426: ~2.8 requests per item).
        children: Dict[str, List[Dict[str, Any]]] = {}
        for item in items:
            if item.parent_item:
                children.setdefault(item.parent_item, []).append(item.raw_data)
        self._write_zip(output, manifest, items, children, on_item_processed)

    def _write_zip(
        self,
        output: str | IO[bytes],
        manifest: dict,
        items: List[ZoteroItem],
        children: Dict[str, List[Dict[str, Any]]],
        on_item_processed: Optional[Callable[[ZoteroItem], None]] = None,
    ) -> None:
        errors: List[str] = []
        processed_keys: Set[str] = set()

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
                        item, children.get(item.key, []), zf, manifest, errors, writer, processed_keys
                    )

                    # Notify progress
                    if on_item_processed:
                        on_item_processed(item)
                writer.close()
                data_file.close()

                # Write Manifest (including updated file_map)
                zf.writestr("manifest.json", json.dumps(manifest, indent=2))

                # Write Data
                zf.write(data_path, "data.json")

                # Write collections structure for library backups
                if manifest["scope_type"] == "library":
                    collections = self.gateway.get_all_collections()
                    zf.writestr("collections.json", json.dumps(collections, separators=(",", ":")))

                # Write Errors if any
                if errors:
                    zf.writestr("errors.log", "\n".join(errors))

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
        if data.get("itemType") == "attachment" and data.get("linkMode") in [
            "imported_file",
            "linked_file",
        ]:
            if item.key in manifest["file_map"]:
                return

            filename = data.get("filename") or data.get("title")
            if filename:
                safe_filename = os.path.basename(str(filename).replace("\\", "/"))
                if not safe_filename or safe_filename in (".", ".."):
                    safe_filename = item.key
                p_key = parent_key or data.get("parentItem") or "orphan"
                storage_path = f"attachments/{p_key}/{safe_filename}"
                try:
                    with tempfile.NamedTemporaryFile(delete=False) as tf:
                        temp_path = tf.name

                    if self.gateway.download_attachment(item.key, temp_path):
                        zf.write(temp_path, storage_path, compress_type=_compression_for(data))

                        # Calculate SHA-256 checksum [SPEC-ZAF-001]
                        import hashlib

                        sha256_hash = hashlib.sha256()
                        with open(temp_path, "rb") as f:
                            for byte_block in iter(lambda: f.read(4096), b""):
                                sha256_hash.update(byte_block)
                        checksum = sha256_hash.hexdigest()

                        manifest["file_map"][item.key] = {
                            "path": storage_path,
                            "checksum": checksum,
                        }
                    else:
                        errors.append(f"Failed to download attachment {item.key} ({filename})")

                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except Exception as e:
                    errors.append(f"Error processing attachment {item.key}: {str(e)}")
                    if "temp_path" in locals() and os.path.exists(temp_path):
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
    ) -> None:
        """
        Adds an item's children (attachments/notes) after it. They come in
        full from the listing, so none is fetched again (Issue #426) unless
        only its key is known.
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
                child = self.gateway.get_item(child_key)
            if not child:
                errors.append(f"Could not fetch child item {child_key} for parent {item.key}")
                continue
            writer.add(child.raw_data)
            processed_keys.add(child.key)

            # Download attachment file if the child is an attachment
            self._download_attachment_file(child, zf, manifest, errors, parent_key=item.key)


def _has_children(item: ZoteroItem) -> bool:
    return item.item_type not in ("attachment", "note", "annotation")


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
