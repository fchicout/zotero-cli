import unittest
from unittest.mock import Mock, patch, MagicMock
from paper2zotero.infra.arxiv_lib import ArxivLibGateway
from paper2zotero.core.models import ArxivPaper
import arxiv

class TestArxivLibGateway(unittest.TestCase):
    @patch('paper2zotero.infra.arxiv_lib.arxiv.Client')
    @patch('paper2zotero.infra.arxiv_lib.arxiv.Search')
    def test_search_returns_papers(self, MockSearch, MockClient):
        # Setup mocks
        mock_client_instance = MockClient.return_value
        
        # Create mock result objects that mimic arxiv.Result
        mock_result1 = MagicMock()
        mock_result1.get_short_id.return_value = "2301.00001v1"
        mock_result1.title = "Title 1"
        mock_result1.summary = "Abstract 1"

        mock_result2 = MagicMock()
        mock_result2.get_short_id.return_value = "2301.00002v1"
        mock_result2.title = "Title 2"
        mock_result2.summary = "Abstract 2"

        # The client.results() returns an iterator
        mock_client_instance.results.return_value = iter([mock_result1, mock_result2])

        # Action
        gateway = ArxivLibGateway()
        papers = list(gateway.search("test query", limit=2))

        # Assertion
        self.assertEqual(len(papers), 2)
        
        self.assertIsInstance(papers[0], ArxivPaper)
        self.assertEqual(papers[0].arxiv_id, "2301.00001v1")
        self.assertEqual(papers[0].title, "Title 1")
        self.assertEqual(papers[0].abstract, "Abstract 1")

        self.assertIsInstance(papers[1], ArxivPaper)
        self.assertEqual(papers[1].arxiv_id, "2301.00002v1")

        # Verify arguments to arxiv.Search
        MockSearch.assert_called_once_with(
            query="test query",
            max_results=2,
            sort_by=arxiv.SortCriterion.Relevance
        )

if __name__ == '__main__':
    unittest.main()
