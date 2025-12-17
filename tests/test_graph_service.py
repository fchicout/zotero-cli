import unittest
from unittest.mock import Mock, MagicMock
from paper2zotero.core.interfaces import ZoteroGateway
from paper2zotero.core.services.metadata_aggregator import MetadataAggregatorService
from paper2zotero.core.zotero_item import ZoteroItem
from paper2zotero.core.models import ResearchPaper
from paper2zotero.core.services.graph_service import CitationGraphService

class TestCitationGraphService(unittest.TestCase):
    def setUp(self):
        self.mock_zotero_gateway = Mock(spec=ZoteroGateway)
        self.mock_metadata_service = Mock(spec=MetadataAggregatorService)
        self.service = CitationGraphService(self.mock_zotero_gateway, self.mock_metadata_service)

        self.mock_zotero_gateway.get_collection_id_by_name.return_value = "COL_ID"
    
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

    def test_build_graph_simple_case(self):
        # Setup mock Zotero items
        item_a = self._create_zotero_item("KEY_A", "Paper A", "10.1/A")
        item_b = self._create_zotero_item("KEY_B", "Paper B", "10.1/B")
        item_c = self._create_zotero_item("KEY_C", "Paper C", "10.1/C")
        
        self.mock_zotero_gateway.get_items_in_collection.return_value = iter([item_a, item_b, item_c])

        # Setup enriched metadata mocks
        def get_metadata_side_effect(doi):
            if doi == "10.1/A":
                return ResearchPaper(title="A", abstract="", references=["10.1/B", "10.999/external"])
            if doi == "10.1/B":
                return ResearchPaper(title="B", abstract="", references=["10.1/C"])
            return ResearchPaper(title="C", abstract="", references=[])

        self.mock_metadata_service.get_enriched_metadata.side_effect = get_metadata_side_effect

        graph_dot = self.service.build_graph(["My Collection"])
        
        self.assertIn("digraph CitationGraph {", graph_dot)
        self.assertIn('  "10.1/A" -> "10.1/B";', graph_dot)
        self.assertIn('  "10.1/B" -> "10.1/C";', graph_dot)
        self.assertNotIn('10.999/external', graph_dot)

    def test_build_graph_no_references(self):
        item_a = self._create_zotero_item("KEY_A", "Paper A", "10.1/A")
        self.mock_zotero_gateway.get_items_in_collection.return_value = iter([item_a])
        self.mock_metadata_service.get_enriched_metadata.return_value = ResearchPaper(title="A", abstract="", references=[])

        graph_dot = self.service.build_graph(["My Collection"])
        
        self.assertIn('  "10.1/A" [label="Paper A"];', graph_dot)
        self.assertNotIn("->", graph_dot)

if __name__ == '__main__':
    unittest.main()