import os
import tempfile
from typing import Optional

import requests

from zotero_cli.core.interfaces import (
    AttachmentRepository,
    CollectionRepository,
    ItemRepository,
    NoteRepository,
)
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService


class AttachmentService:
    def __init__(
        self,
        item_repo: ItemRepository,
        collection_repo: CollectionRepository,
        attachment_repo: AttachmentRepository,
        note_repo: NoteRepository,
        metadata_aggregator: MetadataAggregatorService,
    ):
        self.item_repo = item_repo
        self.collection_repo = collection_repo
        self.attachment_repo = attachment_repo
        self.note_repo = note_repo
        self.metadata_aggregator = metadata_aggregator

    def attach_pdfs_to_collection(self, collection_name: str) -> int:
        col_id = self.collection_repo.get_collection_id_by_name(collection_name)
        if not col_id:
            print(f"Collection '{collection_name}' not found.")
            return 0

        success_count = 0
        items = self.collection_repo.get_items_in_collection(col_id)

        for item in items:
            if self.attach_pdf_to_item(item.key):
                success_count += 1

        return success_count

    def attach_pdf_to_item(self, item_key: str) -> bool:
        """Attempts to find and attach a PDF to a single item."""
        # 1. Check if item exists and already has PDF
        item = self.item_repo.get_item(item_key)
        if not item:
            print(f"Item '{item_key}' not found.")
            return False

        if self._has_pdf_attachment(item_key):
            return False

        identifier = item.doi or item.arxiv_id
        if not identifier:
            return False

        print(f"Checking PDF for: {item.title} ({identifier})")

        # 2. Get Metadata (PDF URL)
        enriched = self.metadata_aggregator.get_enriched_metadata(identifier)
        if not enriched or not enriched.pdf_url:
            print("  No PDF URL found.")
            return False

        print(f"  Found PDF URL: {enriched.pdf_url}")

        # 3. Download
        pdf_path = self._download_file(enriched.pdf_url)
        if not pdf_path:
            print("  Failed to download PDF.")
            return False

        # 4. Upload
        print("  Uploading to Zotero...")
        success = self.attachment_repo.upload_attachment(item_key, pdf_path)

        # Cleanup
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

        if success:
            print("  Success!")
        else:
            print("  Upload failed.")

        return success

    def remove_attachments_from_collection(
        self, collection_name: str, verbose: bool = False
    ) -> int:
        col_id = self.collection_repo.get_collection_id_by_name(collection_name)
        if not col_id:
            print(f"Collection '{collection_name}' not found.")
            return 0

        items = self.collection_repo.get_items_in_collection(col_id)
        count = 0
        for item in items:
            count += self.remove_attachments_from_item(item.key, verbose)
        return count

    def remove_attachments_from_item(self, item_key: str, verbose: bool = False) -> int:
        children = self.note_repo.get_item_children(item_key)
        count = 0
        for child in children:
            if child.get("data", {}).get("itemType") == "attachment":
                if self.item_repo.delete_item(child["key"], child["version"]):
                    count += 1
                    if verbose:
                        print(f"Removed attachment: {child['key']}")
        return count

    def _has_pdf_attachment(self, item_key: str) -> bool:
        children = self.note_repo.get_item_children(item_key)
        for child in children:
            if (
                child.get("data", {}).get("itemType") == "attachment"
                and child.get("data", {}).get("linkMode") == "imported_file"
                and child.get("data", {}).get("contentType", "") == "application/pdf"
            ):
                return True
        return False

    def _download_file(self, url: str) -> Optional[str]:
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            # Create temp file
            fd, path = tempfile.mkstemp(suffix=".pdf")
            with os.fdopen(fd, "wb") as tmp:
                for chunk in response.iter_content(chunk_size=8192):
                    tmp.write(chunk)
            return path
        except Exception as e:
            print(f"Download error: {e}")
            return None
