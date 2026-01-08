import unittest
from unittest.mock import Mock, MagicMock
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.core.services.audit_service import CollectionAuditor, AuditReport

class TestCollectionAuditor(unittest.TestCase):
    def setUp(self):
        self.mock_gateway = Mock(spec=ZoteroGateway)
        self.auditor = CollectionAuditor(self.mock_gateway)
        self.mock_gateway.get_collection_id_by_name.return_value = "COL_ID"
        self.children_data = {} # To store children for each item key
        self.mock_gateway.get_item_children.side_effect = lambda k: self.children_data.get(k, [])


    def _create_mock_item(self, key, title=None, abstract=None, doi=None, arxiv_id=None, has_pdf=False):
        raw_item = {
            'key': key,
            'data': {
                'version': 1,
                'itemType': 'journalArticle',
                'title': title,
                'abstractNote': abstract,
                'DOI': doi,
                'extra': f"arXiv: {arxiv_id}" if arxiv_id else '',
            }
        }
        item = ZoteroItem.from_raw_zotero_item(raw_item)
        
        if has_pdf:
            self.children_data[key] = [{
                'key': 'ATT' + key, # Unique attachment key
                'data': {
                    'itemType': 'attachment',
                    'linkMode': 'imported_file',
                    'filename': 'paper.pdf'
                }
            }]
        
        return item

    def test_audit_collection_full_compliance(self):
        item1 = self._create_mock_item("ITEM1", "Title 1", "Abstract 1", "10.1/1", None, True)
        item2 = self._create_mock_item("ITEM2", "Title 2", "Abstract 2", None, "2301.00001", True)
        self.mock_gateway.get_items_in_collection.return_value = iter([item1, item2])
        
        report = self.auditor.audit_collection("Test Collection")
        
        self.assertIsNotNone(report)
        self.assertEqual(report.total_items, 2)
        self.assertEqual(len(report.items_missing_id), 0)
        self.assertEqual(len(report.items_missing_title), 0)
        self.assertEqual(len(report.items_missing_abstract), 0)
        self.assertEqual(len(report.items_missing_pdf), 0)

    def test_audit_collection_missing_attributes(self):
        item1 = self._create_mock_item("ITEM1", None, "Abstract 1", "10.1/1", None, False) # Missing title, pdf
        item2 = self._create_mock_item("ITEM2", "Title 2", None, None, None, True) # Missing abstract, id
        item3 = self._create_mock_item("ITEM3", "Title 3", "Abstract 3", None, None, False) # Missing ID, PDF
        self.mock_gateway.get_items_in_collection.return_value = iter([item1, item2, item3])
        
        report = self.auditor.audit_collection("Test Collection")
        
        self.assertIsNotNone(report)
        self.assertEqual(report.total_items, 3)
        
        self.assertEqual(len(report.items_missing_id), 2)
        self.assertIn(item2, report.items_missing_id)
        self.assertIn(item3, report.items_missing_id)

        self.assertEqual(len(report.items_missing_title), 1)
        self.assertIn(item1, report.items_missing_title)

        self.assertEqual(len(report.items_missing_abstract), 1)
        self.assertIn(item2, report.items_missing_abstract)

        self.assertEqual(len(report.items_missing_pdf), 2)
        self.assertIn(item1, report.items_missing_pdf)
        self.assertIn(item3, report.items_missing_pdf)

    def test_audit_collection_not_found(self):
        self.mock_gateway.get_collection_id_by_name.return_value = None
        report = self.auditor.audit_collection("Non Existent Collection")
        self.assertIsNone(report)

if __name__ == '__main__':
    unittest.main()
