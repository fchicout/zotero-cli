import os
import tempfile
import warnings
from typing import Optional

import requests

from zotero_cli.core.interfaces import (
    AttachmentRepository,
    CollectionRepository,
    ItemRepository,
    NoteRepository,
)
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService
from zotero_cli.core.services.purge_service import PurgeService


class AttachmentService:
    def __init__(
        self,
        item_repo: ItemRepository,
        collection_repo: CollectionRepository,
        attachment_repo: AttachmentRepository,
        note_repo: NoteRepository,
        metadata_aggregator: MetadataAggregatorService,
        purge_service: Optional[PurgeService] = None,
    ):
        self.item_repo = item_repo
        self.collection_repo = collection_repo
        self.attachment_repo = attachment_repo
        self.note_repo = note_repo
        self.metadata_aggregator = metadata_aggregator
        self.purge_service = purge_service

    def _get_purge_service(self) -> PurgeService:
        if not self.purge_service:
            # This is a bit hacky but avoids refactoring all factory calls at once if needed,
            # though we will update the factory.
            from zotero_cli.infra.factory import GatewayFactory

            self.purge_service = GatewayFactory.get_purge_service()
        return self.purge_service

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
        self, collection_name: str, dry_run: bool = True
    ) -> int:
        warnings.warn(
            "AttachmentService.remove_attachments_from_collection is deprecated and will be removed in Phase B. Use PurgeService.purge_collection_assets instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        col_id = self.collection_repo.get_collection_id_by_name(collection_name)
        if not col_id:
            print(f"Collection '{collection_name}' not found.")
            return 0

        item_keys = [item.key for item in self.collection_repo.get_items_in_collection(col_id)]
        if not item_keys:
            return 0

        stats = self._get_purge_service().purge_attachments(item_keys, dry_run=dry_run)
        return stats["deleted"] if not dry_run else stats["skipped"]

    def remove_attachments_from_item(self, item_key: str, dry_run: bool = True) -> int:
        warnings.warn(
            "AttachmentService.remove_attachments_from_item is deprecated and will be removed in Phase B. Use PurgeService.purge_item_assets instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        stats = self._get_purge_service().purge_attachments([item_key], dry_run=dry_run)
        return stats["deleted"] if not dry_run else stats["skipped"]

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
