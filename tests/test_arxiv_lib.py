import unittest
from unittest.mock import Mock, patch, MagicMock
from paper2zotero.infra.arxiv_lib import ArxivLibGateway
from paper2zotero.core.models import ResearchPaper
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
        mock_result1.authors = [Mock(name="Author 1"), Mock(name="Author 2")]
        # Mocking the name attribute of the author objects is tricky with MagicMock(name=...) 
        # because 'name' is a special argument. Better to set it explicitly.
        mock_result1.authors[0].name = "Author 1"
        mock_result1.authors[1].name = "Author 2"
        mock_result1.published.year = 2023
        mock_result1.doi = "10.1234/doi1"
        mock_result1.pdf_url = "http://pdf1"
        mock_result1.journal_ref = "Journal 1"

        mock_result2 = MagicMock()
        mock_result2.get_short_id.return_value = "2301.00002v1"
        mock_result2.title = "Title 2"
        mock_result2.summary = "Abstract 2"
        mock_result2.authors = []
        mock_result2.published = None
        mock_result2.doi = None
        mock_result2.pdf_url = None
        mock_result2.journal_ref = None

        # The client.results() returns an iterator
        mock_client_instance.results.return_value = iter([mock_result1, mock_result2])

        # Action
        gateway = ArxivLibGateway()
        papers = list(gateway.search("test query", limit=2))

        # Assertion
        self.assertEqual(len(papers), 2)
        
        self.assertIsInstance(papers[0], ResearchPaper)
        self.assertEqual(papers[0].arxiv_id, "2301.00001v1")
        self.assertEqual(papers[0].title, "Title 1")
        self.assertEqual(papers[0].abstract, "Abstract 1")
        self.assertEqual(papers[0].authors, ["Author 1", "Author 2"])
        self.assertEqual(papers[0].year, "2023")
        self.assertEqual(papers[0].doi, "10.1234/doi1")
        self.assertEqual(papers[0].url, "http://pdf1")
        self.assertEqual(papers[0].publication, "Journal 1")

        self.assertIsInstance(papers[1], ResearchPaper)
        self.assertEqual(papers[1].arxiv_id, "2301.00002v1")
        self.assertEqual(papers[1].year, None)

        # Verify arguments to arxiv.Search
        MockSearch.assert_called_once_with(
            query="test query",
            max_results=2,
            sort_by=arxiv.SortCriterion.Relevance
        )

if __name__ == '__main__':
    unittest.main()