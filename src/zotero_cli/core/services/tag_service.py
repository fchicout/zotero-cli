from typing import List, Optional
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.zotero_item import ZoteroItem

class TagService:
    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

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

    def remove_tags_from_item(self, item_key: str, item: ZoteroItem, tags_to_remove: List[str]) -> bool:
        """
        Removes specific tags from an item.
        """
        current_tags = set(item.tags)
        to_remove = set(tags_to_remove)
        
        if not to_remove.intersection(current_tags):
            return True # Nothing to remove

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

    def delete_tag(self, tag: str) -> int:
        """
        Deletes a tag from all items in the library.
        Returns the number of items updated.
        """
        count = 0
        for item in self.gateway.get_items_by_tag(tag):
            current_tags = set(item.tags)
            if tag in current_tags:
                current_tags.remove(tag)
                if self._update_tags(item.key, item.version, list(current_tags)):
                    count += 1
        return count

    def _update_tags(self, item_key: str, version: int, tags: List[str]) -> bool:
        # Zotero API expects tags as a list of objects: [{"tag": "name"}, ...]
        tag_payload = [{"tag": t} for t in tags]
        return self.gateway.update_item_metadata(item_key, version, {"tags": tag_payload})
