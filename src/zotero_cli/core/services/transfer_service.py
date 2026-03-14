import logging
import os
import tempfile
from typing import Optional

from zotero_cli.core.interfaces import ZoteroGateway

logger = logging.getLogger(__name__)


class TransferService:
    """Service for moving items between different Zotero libraries."""

    def __init__(self):
        pass

    def transfer_item(
        self,
        item_key: str,
        source_gateway: ZoteroGateway,
        dest_gateway: ZoteroGateway,
        delete_source: bool = False,
    ) -> Optional[str]:
        """
        Transfers an item (metadata + children) from source to destination gateway.
        Returns the new item key in the destination library.
        """
        # 1. Fetch source item
        source_item = source_gateway.get_item(item_key)
        if not source_item:
            logger.error(f"Source item {item_key} not found.")
            return None

        # 2. Create base item in destination
        # We use create_generic_item with the cleaned data
        dest_item_data = source_item.raw_data.get("data", {}).copy()

        # Remove keys that shouldn't be transferred or will be auto-generated
        for key in ["key", "version", "library", "collections", "relations"]:
            dest_item_data.pop(key, None)

        new_item_key = dest_gateway.create_generic_item(dest_item_data)
        if not new_item_key:
            logger.error("Failed to create item in destination library.")
            return None

        logger.info(f"Created item {new_item_key} in destination library.")

        # 3. Transfer children
        children = source_gateway.get_item_children(item_key)
        for child in children:
            child_data = child.get("data", {})
            item_type = child_data.get("itemType")

            if item_type == "note":
                note_content = child_data.get("note", "")
                dest_gateway.create_note(new_item_key, note_content)
                logger.debug(f"Transferred note to {new_item_key}")

            elif item_type == "attachment":
                child_key = child.get("key")
                if not child_key:
                    continue
                filename = child_data.get("filename", "attachment.pdf")
                mime_type = child_data.get("contentType", "application/pdf")

                # Only transfer if it's a file
                if child_data.get("linkMode") in ["imported_file", "linked_file"]:
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        local_path = os.path.join(tmp_dir, filename)
                        if source_gateway.download_attachment(child_key, local_path):
                            dest_gateway.upload_attachment(
                                new_item_key, local_path, mime_type=mime_type
                            )
                            logger.debug(f"Transferred attachment {filename} to {new_item_key}")
                        else:
                            logger.warning(f"Failed to download attachment {child_key}")

        # 4. Optional Cleanup
        if delete_source:
            if source_gateway.delete_item(item_key, source_item.version):
                logger.info(f"Deleted source item {item_key}")
            else:
                logger.warning(f"Failed to delete source item {item_key}")

        return new_item_key
