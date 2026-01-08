import unittest
from unittest.mock import Mock
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.core.services.duplicate_service import DuplicateFinder, DuplicateGroup

class TestDuplicateFinder(unittest.TestCase):
    def setUp(self):
        self.mock_gateway = Mock(spec=ZoteroGateway)
        self.finder = DuplicateFinder(self.mock_gateway)
        
        # Setup mock collection IDs
        self.mock_gateway.get_collection_id_by_name.side_effect = \
            lambda name: "ID_COL_A" if name == "Collection A" else \
                         ("ID_COL_B" if name == "Collection B" else None)

    def _create_zotero_item(self, key, title=None, doi=None):
        raw_item = {
            'key': key,
            'data': {
                'version': 1,
                'itemType': 'journalArticle',
                'title': title,
                'DOI': doi,
            }
        }
        return ZoteroItem.from_raw_zotero_item(raw_item)

    def test_find_duplicates_no_duplicates(self):
        item1 = self._create_zotero_item("KEY1", "Unique Title 1", "10.1/1")
        item2 = self._create_zotero_item("KEY2", "Unique Title 2", "10.1/2")
        self.mock_gateway.get_items_in_collection.side_effect = [
            iter([item1]), # Collection A
            iter([item2])  # Collection B
        ]
        
        duplicates = self.finder.find_duplicates(["Collection A", "Collection B"])
        self.assertEqual(len(duplicates), 0)

    def test_find_duplicates_by_doi(self):
        item1 = self._create_zotero_item("KEY1", "Title A", "10.1/DUPLICATE")
        item2 = self._create_zotero_item("KEY2", "Title B", "10.1/DUPLICATE")
        item3 = self._create_zotero_item("KEY3", "Another Title", "10.1/UNIQUE")
        
        self.mock_gateway.get_items_in_collection.side_effect = [
            iter([item1, item3]), # Collection A
            iter([item2])          # Collection B
        ]

        duplicates = self.finder.find_duplicates(["Collection A", "Collection B"])
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0].identifier_key, "DOI: 10.1/duplicate")
        self.assertCountEqual(duplicates[0].items, [item1, item2])

    def test_find_duplicates_by_title(self):
        item1 = self._create_zotero_item("KEY1", "Duplicate Title", None)
        item2 = self._create_zotero_item("KEY2", "Duplicate Title", None)
        item3 = self._create_zotero_item("KEY3", "Unique Title", None)

        self.mock_gateway.get_items_in_collection.side_effect = [
            iter([item1, item3]),
            iter([item2])
        ]
        
        duplicates = self.finder.find_duplicates(["Collection A", "Collection B"])
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0].identifier_key, "TITLE: duplicate title")
        self.assertCountEqual(duplicates[0].items, [item1, item2])

    def test_find_duplicates_mixed_identifiers(self):
        # Same DOI, different title
        item_doi_1 = self._create_zotero_item("KEY_DOI_1", "Original Title", "10.1/MIXED")
        item_doi_2 = self._create_zotero_item("KEY_DOI_2", "Modified Title", "10.1/MIXED")
        
        # Same title, no DOI
        item_title_1 = self._create_zotero_item("KEY_TITLE_1", "Common Title", None)
        item_title_2 = self._create_zotero_item("KEY_TITLE_2", "Common Title", None)

        # Unique item
        item_unique = self._create_zotero_item("KEY_UNIQUE", "One Of A Kind", "10.1/UNIQUE_ID")

        self.mock_gateway.get_items_in_collection.side_effect = [
            iter([item_doi_1, item_title_1, item_unique]),
            iter([item_doi_2, item_title_2])
        ]

        duplicates = self.finder.find_duplicates(["Collection A", "Collection B"])
        self.assertEqual(len(duplicates), 2)
        
        doi_group = next(g for g in duplicates if g.identifier_key == "DOI: 10.1/mixed")
        self.assertCountEqual(doi_group.items, [item_doi_1, item_doi_2])

        title_group = next(g for g in duplicates if g.identifier_key == "TITLE: common title")
        self.assertCountEqual(title_group.items, [item_title_1, item_title_2])

    def test_find_duplicates_with_missing_collection(self):
        item1 = self._create_zotero_item("KEY1", "Title 1", "10.1/1")
        self.mock_gateway.get_items_in_collection.side_effect = [
            iter([item1]),
            iter([]) # For the missing collection, it would effectively return empty
        ]
        
        duplicates = self.finder.find_duplicates(["Collection A", "Non Existent Collection"])
        self.assertEqual(len(duplicates), 0) # No duplicates since only one collection is processed
        
        # Should also test the warning message, but that's harder with unittest.mock

    def test_normalization_doi(self):
        self.assertEqual(self.finder._normalize_doi("10.123/ABC"), "10.123/abc")
        self.assertEqual(self.finder._normalize_doi(" 10.123/ABC "), "10.123/abc")

    def test_normalization_title(self):
        self.assertEqual(self.finder._normalize_title("A Title. With Punctuation!"), "a title with punctuation")
        self.assertEqual(self.finder._normalize_title("  Another  Title  "), "another title")
        self.assertEqual(self.finder._normalize_title("Résumé paper"), "resume paper") # NFKC normalization
