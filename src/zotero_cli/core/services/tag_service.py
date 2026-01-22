from typing import List, Optional

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.purge_service import PurgeService
from zotero_cli.core.zotero_item import ZoteroItem


class TagService:
    def __init__(self, gateway: ZoteroGateway, purge_service: Optional[PurgeService] = None):
        self.gateway = gateway
        self.purge_service = purge_service or PurgeService(gateway)

    def list_tags(self) -> List[str]:
        """Returns a list of all unique tags in the library."""
        return self.gateway.get_tags()

    def add_tags_to_item(self, item_key: str, item: ZoteroItem, tags_to_add: List[str]) -> bool:
        """
        Adds tags to an item. Preserves existing tags.
        """
        current_tags = set(item.tags)
        new_tags = set(tags_to_add)

        # If all new tags are already present, skip update
        if new_tags.issubset(current_tags):
            return True

        updated_tags = list(current_tags.union(new_tags))
        return self._update_tags(item.key, item.version, updated_tags)

    def remove_tags_from_item(
        self, item_key: str, item: ZoteroItem, tags_to_remove: List[str]
    ) -> bool:
        """
        Removes specific tags from an item.
        """
        current_tags = set(item.tags)
        to_remove = set(tags_to_remove)

        if not to_remove.intersection(current_tags):
            return True  # Nothing to remove

        updated_tags = list(current_tags - to_remove)
        return self._update_tags(item.key, item.version, updated_tags)

    def rename_tag(self, old_tag: str, new_tag: str) -> int:
        """
        Renames a tag across the entire library.
        Returns the number of items updated.
        """
        count = 0
        for item in self.gateway.get_items_by_tag(old_tag):
            # Atomic-like update: remove old, add new
            current_tags = set(item.tags)
            if old_tag in current_tags:
                current_tags.remove(old_tag)
                current_tags.add(new_tag)
                if self._update_tags(item.key, item.version, list(current_tags)):
                    count += 1
        return count

    def delete_tag(self, tag: str, dry_run: bool = False) -> int:
        """
        Deletes a tag from all items in the library.
        Returns the number of items updated.
        """
        item_keys = [item.key for item in self.gateway.get_items_by_tag(tag)]
        if not item_keys:
            return 0

        stats = self.purge_service.purge_tags(item_keys, tag_name=tag, dry_run=dry_run)
        return stats["deleted"] if not dry_run else stats["skipped"]

    def purge_tags_from_collection(self, collection_name: str, dry_run: bool = False) -> int:
        """
        Removes all tags from all items in a specific collection.
        """
        col_id = self.gateway.get_collection_id_by_name(collection_name)
        if not col_id:
            return 0

        item_keys = [item.key for item in self.gateway.get_items_in_collection(col_id)]
        if not item_keys:
            return 0

        stats = self.purge_service.purge_tags(item_keys, tag_name=None, dry_run=dry_run)
        return stats["deleted"] if not dry_run else stats["skipped"]

    def _update_tags(self, item_key: str, version: int, tags: List[str]) -> bool:
        # Zotero API expects tags as a list of objects: [{"tag": "name"}, ...]
        tag_payload = [{"tag": t} for t in tags]
        return self.gateway.update_item_metadata(item_key, version, {"tags": tag_payload})
