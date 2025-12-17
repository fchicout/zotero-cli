import unittest
from unittest.mock import Mock
from paper2zotero.core.models import ResearchPaper
from paper2zotero.core.services.metadata_aggregator import MetadataAggregatorService

class TestMetadataAggregatorService(unittest.TestCase):
    def test_merge_logic(self):
        # Provider 1 (e.g., CrossRef): Good dates, DOI, short abstract
        p1 = ResearchPaper(
            title="A SURVEY ON LLMS",
            abstract="Short abstract.",
            authors=["A. Smith", "B. Jones"],
            year="2023",
            doi="10.1000/1",
            references=["10.1/A"]
        )

        # Provider 2 (e.g., Semantic Scholar): Good title, long abstract, more authors
        p2 = ResearchPaper(
            title="A Survey on LLMs",
            abstract="A very long and detailed abstract about Large Language Models.",
            authors=["Alice Smith", "Bob Jones", "Charlie Day"],
            year=None,
            doi="10.1000/1",
            references=["10.1/B"]
        )

        service = MetadataAggregatorService([])
        merged = service._merge_metadata([p1, p2])

        # Assertions
        self.assertEqual(merged.title, "A Survey on LLMs") # Clean title preferred
        self.assertEqual(merged.abstract, p2.abstract) # Longest abstract wins
        self.assertEqual(merged.authors, p2.authors) # Most authors wins
        self.assertEqual(merged.year, "2023") # Existing year wins
        self.assertEqual(merged.doi, "10.1000/1")
        self.assertCountEqual(merged.references, ["10.1/A", "10.1/B"]) # Union of refs

    def test_clean_title(self):
        service = MetadataAggregatorService([])
        self.assertEqual(service._clean_title("ALL CAPS TITLE"), "ALL CAPS TITLE")
        self.assertEqual(service._clean_title("Normal Title"), "Normal Title")
        self.assertEqual(service._clean_title("  Spaces  "), "Spaces")

if __name__ == '__main__':
    unittest.main()
