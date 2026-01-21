from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.collection_service import CollectionService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_repos():
    item_repo = MagicMock()
    coll_repo = MagicMock()
    return item_repo, coll_repo


def test_delete_collection_recursive_with_subcollections(mock_repos):
    item_repo, coll_repo = mock_repos
    service = CollectionService(item_repo, coll_repo)

    # Setup: Root -> Parent -> Sub
    parent_id = "PARENT"
    sub_id = "SUB"

    item_p = ZoteroItem(key="ITEM_P", version=1, item_type="journalArticle", raw_data={})
    item_s = ZoteroItem(key="ITEM_S", version=1, item_type="journalArticle", raw_data={})

    # mock get_all_collections to return parent and sub
    coll_repo.get_all_collections.return_value = [
        {"key": parent_id, "version": 1, "data": {"name": "Parent", "parentCollection": False}},
        {"key": sub_id, "version": 1, "data": {"name": "Sub", "parentCollection": parent_id}},
    ]

    # mock items in collections
    def get_items(cid, top_only=False):
        if cid == parent_id:
            return iter([item_p])
        if cid == sub_id:
            return iter([item_s])
        return iter([])

    coll_repo.get_items_in_collection.side_effect = get_items
    item_repo.delete_item.return_value = True
    coll_repo.delete_collection.return_value = True

    # Execute
    service.delete_collection(parent_id, 1, recursive=True)

    # Verify: Should have deleted BOTH items
    # The current implementation only deletes items in the target collection.
    # So ITEM_S will NOT be deleted.

    # item_repo.delete_item.assert_any_call("ITEM_P", 1)
    # item_repo.delete_item.assert_any_call("ITEM_S", 1) # THIS SHOULD FAIL with current code

    # Verified: It will fail because current code doesn't look at sub-collections.
    calls = [c[0][0] for c in item_repo.delete_item.call_args_list]
    assert "ITEM_P" in calls
    assert "ITEM_S" in calls  # This will fail
