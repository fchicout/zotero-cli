import unittest
from zotero_cli.core.zotero_item import ZoteroItem

class TestZoteroItem(unittest.TestCase):
    def test_from_raw_zotero_item_full_data(self):
        raw_item = {
            'key': 'ABC123DEF456',
            'data': {
                'version': 123,
                'itemType': 'journalArticle',
                'title': 'Test Article Title',
                'abstractNote': 'This is a test abstract.',
                'DOI': '10.1234/test.article',
                'extra': 'Some other info\narXiv: 2301.00001v2',
                'url': 'http://example.com/test',
                'collections': ['COL1', 'COL2']
            }
        }
        item = ZoteroItem.from_raw_zotero_item(raw_item)
        self.assertEqual(item.key, 'ABC123DEF456')
        self.assertEqual(item.version, 123)
        self.assertEqual(item.item_type, 'journalArticle')
        self.assertEqual(item.title, 'Test Article Title')
        self.assertEqual(item.abstract, 'This is a test abstract.')
        self.assertEqual(item.doi, '10.1234/test.article')
        self.assertEqual(item.arxiv_id, '2301.00001v2')
        self.assertEqual(item.url, 'http://example.com/test')
        self.assertEqual(item.collections, ['COL1', 'COL2'])
        self.assertFalse(item.has_pdf) # Should be false by default

    def test_from_raw_zotero_item_minimal_data(self):
        raw_item = {
            'key': 'XYZ789',
            'data': {
                'version': 1,
                'itemType': 'book',
                'title': 'Minimal Book',
                'collections': []
            }
        }
        item = ZoteroItem.from_raw_zotero_item(raw_item)
        self.assertEqual(item.key, 'XYZ789')
        self.assertEqual(item.version, 1)
        self.assertEqual(item.item_type, 'book')
        self.assertEqual(item.title, 'Minimal Book')
        self.assertIsNone(item.abstract)
        self.assertIsNone(item.doi)
        self.assertIsNone(item.arxiv_id)
        self.assertIsNone(item.url)
        self.assertEqual(item.collections, [])
        self.assertFalse(item.has_pdf)

    def test_from_raw_zotero_item_arxiv_from_url(self):
        raw_item = {
            'key': 'ARXIV123',
            'data': {
                'version': 5,
                'itemType': 'preprint',
                'title': 'arXiv Paper from URL',
                'url': 'https://arxiv.org/abs/2403.12345'
            }
        }
        item = ZoteroItem.from_raw_zotero_item(raw_item)
        self.assertEqual(item.arxiv_id, '2403.12345')

    def test_has_identifier(self):
        item_with_doi = ZoteroItem.from_raw_zotero_item({
            'key': 'A', 'data': {'DOI': '1.2/3', 'version':1, 'itemType': 'journalArticle'}
        })
        self.assertTrue(item_with_doi.has_identifier())

        item_with_arxiv = ZoteroItem.from_raw_zotero_item({
            'key': 'B', 'data': {'extra': 'arXiv: 1234.5678', 'version':1, 'itemType': 'journalArticle'}
        })
        self.assertTrue(item_with_arxiv.has_identifier())

        item_without_id = ZoteroItem.from_raw_zotero_item({
            'key': 'C', 'data': {'title': 'No ID', 'version':1, 'itemType': 'journalArticle'}
        })
        self.assertFalse(item_without_id.has_identifier())

if __name__ == '__main__':
    unittest.main()
