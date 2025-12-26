import unittest
from paper2zotero.core.services.arxiv_query_parser import ArxivQueryParser

class TestArxivQueryParser(unittest.TestCase):
    def setUp(self):
        self.parser = ArxivQueryParser()

    def test_parse_complex_query(self):
        query_str = "order: -announced_date_first; size: 200; date_range: from 2020-01-01 ; classification: Computer Science (cs); include_cross_list: True; terms: AND all='cybersecurity' OR 'cyber security' OR 'cyber'; AND all=threat* OR anomal*; AND all=detection OR identification; AND all=LLM* OR language model* OR large language model*"
        
        params = self.parser.parse(query_str)
        
        self.assertEqual(params.max_results, 200)
        self.assertEqual(params.sort_by, "submittedDate")
        self.assertEqual(params.sort_order, "descending")
        
        # Verify query structure
        self.assertIn("cat:cs.*", params.query)
        self.assertIn("submittedDate:[202001010000 TO", params.query)
        self.assertIn('all:("cybersecurity" OR "cyber security" OR "cyber")', params.query)
        self.assertIn("all:(threat* OR anomal*)", params.query)
        self.assertIn("all:(detection OR identification)", params.query)
        self.assertIn("all:(LLM* OR language model* OR large language model*)", params.query)

if __name__ == '__main__':
    unittest.main()
