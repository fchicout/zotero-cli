import unittest
from unittest.mock import Mock, MagicMock
from paper2zotero.core.interfaces import ZoteroGateway
from paper2zotero.core.services.collection_service import CollectionService
from paper2zotero.core.zotero_item import ZoteroItem # Import ZoteroItem

class TestCollectionService(unittest.TestCase):
    def setUp(self):
        self.mock_gateway = Mock(spec=ZoteroGateway)
        self.service = CollectionService(self.mock_gateway)
        
        # Setup common return values
        self.mock_gateway.get_collection_id_by_name.side_effect = \
            lambda name: "ID_SRC" if name == "Source" else ("ID_DEST" if name == "Dest" else None)

    def test_move_item_success_doi(self):
        # Mock Item - now converted to ZoteroItem
        raw_item = {
            'key': 'ITEM1',
            'data': {
                'version': 1,
                'DOI': '10.1234/test',
                'collections': ['ID_SRC', 'ID_OTHER']
            }
        }
        item = ZoteroItem.from_raw_zotero_item(raw_item)
        self.mock_gateway.get_items_in_collection.return_value = iter([item])
        self.mock_gateway.update_item_collections.return_value = True

        result = self.service.move_item("Source", "Dest", "10.1234/test")
        
        self.assertTrue(result)
        # Verify call args
        args = self.mock_gateway.update_item_collections.call_args
        self.assertEqual(args[0][0], 'ITEM1') # key
        self.assertEqual(args[0][1], 1) # version
        self.assertIn('ID_DEST', args[0][2])
        self.assertNotIn('ID_SRC', args[0][2])
        self.assertIn('ID_OTHER', args[0][2])

    def test_move_item_not_found(self):
        self.mock_gateway.get_items_in_collection.return_value = iter([])
        result = self.service.move_item("Source", "Dest", "missing")
        self.assertFalse(result)
        self.mock_gateway.update_item_collections.assert_not_called()

    def test_move_item_success_arxiv(self):
         # Mock Item with arXiv in Extra - now converted to ZoteroItem
        raw_item = {
            'key': 'ITEM2',
            'data': {
                'version': 5,
                'extra': 'Some note\narXiv: 2301.00001',
                'collections': ['ID_SRC']
            }
        }
        item = ZoteroItem.from_raw_zotero_item(raw_item)
        self.mock_gateway.get_items_in_collection.return_value = iter([item])
        self.mock_gateway.update_item_collections.return_value = True

        result = self.service.move_item("Source", "Dest", "2301.00001")
        
        self.assertTrue(result)
        
    def test_collections_not_found(self):
        result = self.service.move_item("BadSource", "Dest", "id")
        self.assertFalse(result)
        
        result = self.service.move_item("Source", "BadDest", "id")
        self.assertFalse(result)

    def test_empty_collection_success_simple(self):
        # Setup
        self.mock_gateway.get_collection_id_by_name.side_effect = None # Clear side_effect
        self.mock_gateway.get_collection_id_by_name.return_value = "COLL_ID"
        
        item1 = Mock(spec=ZoteroItem)
        item1.key = "K1"; item1.version = 1
        item2 = Mock(spec=ZoteroItem)
        item2.key = "K2"; item2.version = 2
        
        self.mock_gateway.get_items_in_collection.return_value = iter([item1, item2])
        self.mock_gateway.delete_item.return_value = True

        # Execute
        count = self.service.empty_collection("TargetCol")

        # Verify
        self.assertEqual(count, 2)
        self.mock_gateway.get_collection_id_by_name.assert_called_with("TargetCol")
        self.mock_gateway.get_items_in_collection.assert_called_with("COLL_ID")
        self.assertEqual(self.mock_gateway.delete_item.call_count, 2)

    def test_empty_collection_with_parent_success(self):
        # Setup
        self.mock_gateway.get_all_collections.return_value = [
            {'key': 'PARENT_ID', 'data': {'name': 'ParentCol'}},
            {'key': 'WRONG_CHILD', 'data': {'name': 'ChildCol', 'parentCollection': 'OTHER_ID'}},
            {'key': 'TARGET_ID', 'data': {'name': 'ChildCol', 'parentCollection': 'PARENT_ID'}}
        ]
        
        item1 = Mock(spec=ZoteroItem)
        item1.key = "K1"; item1.version = 1
        
        self.mock_gateway.get_items_in_collection.return_value = iter([item1])
        self.mock_gateway.delete_item.return_value = True

        # Execute
        count = self.service.empty_collection("ChildCol", parent_collection_name="ParentCol")

        # Verify
        self.assertEqual(count, 1)
        self.mock_gateway.get_items_in_collection.assert_called_with("TARGET_ID")
        self.mock_gateway.delete_item.assert_called_once()

    def test_empty_collection_parent_not_found(self):
        self.mock_gateway.get_all_collections.return_value = []
        count = self.service.empty_collection("Child", parent_collection_name="MissingParent")
        self.assertEqual(count, 0)
        self.mock_gateway.delete_item.assert_not_called()

if __name__ == '__main__':
    unittest.main()
