import pytest

from zotero_cli.core.services.arxiv_query_parser import ArxivQueryParser


@pytest.fixture
def parser():
    return ArxivQueryParser()

def test_parse_complex_query(parser):
    query_str = "order: -announced_date_first; size: 200; date_range: from 2020-01-01 ; classification: Computer Science (cs); include_cross_list: True; terms: AND all='cybersecurity' OR 'cyber security' OR 'cyber'; AND all=threat* OR anomal*; AND all=detection OR identification; AND all=LLM* OR language model* OR large language model*"

    params = parser.parse(query_str)

    assert params.max_results == 200
    assert params.sort_by == "submittedDate"
    assert params.sort_order == "descending"

    # Verify query structure
    assert "cat:cs.*" in params.query
    assert "submittedDate:[202001010000 TO" in params.query
    assert 'all:("cybersecurity" OR "cyber security" OR "cyber")' in params.query
    assert "all:(threat* OR anomal*)" in params.query
    assert "all:(detection OR identification)" in params.query
    assert "all:(LLM* OR language model* OR large language model*)" in params.query
