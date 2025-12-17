import unittest
from unittest.mock import Mock, MagicMock
from paper2zotero.core.interfaces import ZoteroGateway
from paper2zotero.core.services.collection_service import CollectionService

class TestCollectionService(unittest.TestCase):
    def setUp(self):
        self.mock_gateway = Mock(spec=ZoteroGateway)
        self.service = CollectionService(self.mock_gateway)
        
        # Setup common return values
        self.mock_gateway.get_collection_id_by_name.side_effect = \
            lambda name: "ID_SRC" if name == "Source" else ("ID_DEST" if name == "Dest" else None)

    def test_move_item_success_doi(self):
        # Mock Item
        item = {
            'key': 'ITEM1',
            'data': {
                'version': 1,
                'DOI': '10.1234/test',
                'collections': ['ID_SRC', 'ID_OTHER']
            }
        }
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
         # Mock Item with arXiv in Extra
        item = {
            'key': 'ITEM2',
            'data': {
                'version': 5,
                'extra': 'Some note\narXiv: 2301.00001',
                'collections': ['ID_SRC']
            }
        }
        self.mock_gateway.get_items_in_collection.return_value = iter([item])
        self.mock_gateway.update_item_collections.return_value = True

        result = self.service.move_item("Source", "Dest", "2301.00001")
        
        self.assertTrue(result)
        
    def test_collections_not_found(self):
        result = self.service.move_item("BadSource", "Dest", "id")
        self.assertFalse(result)
        
        result = self.service.move_item("Source", "BadDest", "id")
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
