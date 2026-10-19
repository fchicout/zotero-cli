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


PINNED = [
    ["", "", 100, "relevance", "descending"],
    [
        "order: -announced_date_first; size: 200; terms: ti=Attention",
        "ti:Attention",
        200,
        "submittedDate",
        "descending",
    ],
    [
        "order: announced_date_last; size: abc; classification: Computer Science (cs); date_range: from 2020-01-01",
        "cat:cs.* AND submittedDate:[202001010000 TO 209901010000]",
        100,
        "submittedDate",
        "ascending",
    ],
    [
        "terms: ti='attention is' OR abs=graph; AND au=Vaswani",
        'ti:("attention is" OR abs=graph) AND au:Vaswani',
        100,
        "relevance",
        "descending",
    ],
    [
        "terms: free text 'quoted'; (ti=a b)",
        '(free text "quoted") AND ((ti=a b))',
        100,
        "relevance",
        "descending",
    ],
    ["size: 50;;; terms: all=a OR b", "all:(a OR b)", 50, "relevance", "descending"],
    ["classification: physics; date_range: sometime", "", 100, "relevance", "descending"],
]


@pytest.mark.parametrize(("dsl", "query", "size", "sort_by", "sort_order"), PINNED)
def test_the_dsl_keeps_translating_the_same_way(dsl, query, size, sort_by, sort_order):
    from zotero_cli.core.services.arxiv_query_parser import ArxivQueryParser

    params = ArxivQueryParser().parse(dsl)

    assert (params.query, params.max_results, params.sort_by, params.sort_order) == (
        query,
        size,
        sort_by,
        sort_order,
    )
