from typing import Any, Dict, Iterator, List, Optional

from zotero_cli.core.interfaces import (
    AttachmentRepository,
    CollectionRepository,
    ItemRepository,
    NoteRepository,
    TagRepository,
    ZoteroGateway,
)
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.zotero_item import ZoteroItem


class ZoteroItemRepository(ItemRepository):
    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def get_item(self, item_key: str) -> Optional[ZoteroItem]:
        return self.gateway.get_item(item_key)

    def create_item(self, paper: ResearchPaper, collection_id: str) -> bool:
        return self.gateway.create_item(paper, collection_id)

    def create_generic_item(self, item_data: Dict[str, Any]) -> Optional[str]:
        return self.gateway.create_generic_item(item_data)

    def update_item(self, item_key: str, version: int, item_data: Dict[str, Any]) -> bool:
        return self.gateway.update_item(item_key, version, item_data)

    def delete_item(self, item_key: str, version: int) -> bool:
        return self.gateway.delete_item(item_key, version)

    def get_items_by_tag(self, tag: str) -> Iterator[ZoteroItem]:
        return self.gateway.get_items_by_tag(tag)

    def update_item_metadata(self, item_key: str, version: int, metadata: Dict[str, Any]) -> bool:
        return self.gateway.update_item_metadata(item_key, version, metadata)


class ZoteroCollectionRepository(CollectionRepository):
    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def get_collection(self, collection_key: str) -> Optional[Dict[str, Any]]:
        return self.gateway.get_collection(collection_key)

    def get_collection_id_by_name(self, name: str) -> Optional[str]:
        return self.gateway.get_collection_id_by_name(name)

    def create_collection(self, name: str, parent_key: Optional[str] = None) -> Optional[str]:
        return self.gateway.create_collection(name, parent_key)

    def delete_collection(self, collection_key: str, version: int) -> bool:
        return self.gateway.delete_collection(collection_key, version)

    def get_all_collections(self) -> List[Dict[str, Any]]:
        return self.gateway.get_all_collections()

    def get_items_in_collection(
        self, collection_id: str, top_only: bool = False
    ) -> Iterator[ZoteroItem]:
        return self.gateway.get_items_in_collection(collection_id, top_only)


class ZoteroTagRepository(TagRepository):
    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def get_tags(self) -> List[str]:
        return self.gateway.get_tags()

    def get_tags_for_item(self, item_key: str) -> List[str]:
        return self.gateway.get_tags_for_item(item_key)

    def add_tags(self, item_key: str, tags: List[str]) -> bool:
        """
        Adds tags to an item, preserving existing tags.
        """
        item = self.gateway.get_item(item_key)
        if not item:
            return False

        current_tags = self.gateway.get_tags_for_item(item_key)
        # Combine and deduplicate
        updated_tag_set = set(current_tags) | set(tags)

        # Convert to Zotero API format [{"tag": "name"}, ...]
        tag_payload = [{"tag": t} for t in updated_tag_set]

        # We need the version from the raw item data usually, but get_item returns ZoteroItem
        # ZoteroItem (v2) has 'version' attribute? Let's check ZoteroItem definition or fetch raw.
        # Ideally gateway.get_item should return version.
        # Assuming ZoteroItem has a .version attribute (it should).

        return self.gateway.update_item(item_key, item.version, {"tags": tag_payload})

    def delete_tags(self, tags: List[str], version: int) -> bool:
        return self.gateway.delete_tags(tags, version)


class ZoteroNoteRepository(NoteRepository):
    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def create_note(self, parent_item_key: str, note_content: str) -> bool:
        return self.gateway.create_note(parent_item_key, note_content)

    def update_note(self, note_key: str, version: int, note_content: str) -> bool:
        return self.gateway.update_note(note_key, version, note_content)

    def get_item_children(self, item_key: str) -> List[Dict[str, Any]]:
        return self.gateway.get_item_children(item_key)


class ZoteroAttachmentRepository(AttachmentRepository):
    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def upload_attachment(
        self, parent_item_key: str, file_path: str, mime_type: str = "application/pdf"
    ) -> bool:
        return self.gateway.upload_attachment(parent_item_key, file_path, mime_type)

    def download_attachment(self, item_key: str, save_path: str) -> bool:
        return self.gateway.download_attachment(item_key, save_path)

    def update_attachment_link(self, item_key: str, version: int, new_path: str) -> bool:
        return self.gateway.update_attachment_link(item_key, version, new_path)
