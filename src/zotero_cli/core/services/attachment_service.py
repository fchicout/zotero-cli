from typing import Optional
import os
import requests
import tempfile
import shutil
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService

class AttachmentService:
    def __init__(self, zotero_gateway: ZoteroGateway, metadata_aggregator: MetadataAggregatorService):
        self.zotero_gateway = zotero_gateway
        self.metadata_aggregator = metadata_aggregator

    def attach_pdfs_to_collection(self, collection_name: str) -> int:
        col_id = self.zotero_gateway.get_collection_id_by_name(collection_name)
        if not col_id:
            print(f"Collection '{collection_name}' not found.")
            return 0

        success_count = 0
        items = self.zotero_gateway.get_items_in_collection(col_id)
        
        for item in items:
            # 1. Check if item needs PDF
            if self._has_pdf_attachment(item.key):
                continue
            
            identifier = item.doi or item.arxiv_id
            if not identifier:
                continue

            print(f"Checking PDF for: {item.title} ({identifier})")

            # 2. Get Metadata (PDF URL)
            enriched = self.metadata_aggregator.get_enriched_metadata(identifier)
            if not enriched or not enriched.pdf_url:
                print("  No PDF URL found.")
                continue

            print(f"  Found PDF URL: {enriched.pdf_url}")

            # 3. Download
            pdf_path = self._download_file(enriched.pdf_url)
            if not pdf_path:
                print("  Failed to download PDF.")
                continue

            # 4. Upload
            print("  Uploading to Zotero...")
            if self.zotero_gateway.upload_attachment(item.key, pdf_path):
                print("  Success!")
                success_count += 1
            else:
                print("  Upload failed.")
            
            # Cleanup
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

        return success_count

    def _has_pdf_attachment(self, item_key: str) -> bool:
        children = self.zotero_gateway.get_item_children(item_key)
        for child in children:
            if child.get('data', {}).get('itemType') == 'attachment' and \
               child.get('data', {}).get('linkMode') == 'imported_file' and \
               child.get('data', {}).get('contentType', '') == 'application/pdf':
                return True
        return False

    def _download_file(self, url: str) -> Optional[str]:
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Create temp file
            fd, path = tempfile.mkstemp(suffix=".pdf")
            with os.fdopen(fd, 'wb') as tmp:
                for chunk in response.iter_content(chunk_size=8192):
                    tmp.write(chunk)
            return path
        except Exception as e:
            print(f"Download error: {e}")
            return None
