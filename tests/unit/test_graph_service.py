from unittest.mock import Mock

import pytest

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.services.graph_service import CitationGraphService
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_zotero_gateway():
    return Mock(spec=ZoteroGateway)


@pytest.fixture
def mock_metadata_service():
    return Mock(spec=MetadataAggregatorService)


@pytest.fixture
def service(mock_zotero_gateway, mock_metadata_service):
    return CitationGraphService(mock_zotero_gateway, mock_metadata_service)


def create_zotero_item(key, title=None, doi=None):
    raw_item = {
        "key": key,
        "data": {
            "version": 1,
            "itemType": "journalArticle",
            "title": title,
            "DOI": doi,
        },
    }
    return ZoteroItem.from_raw_zotero_item(raw_item)


def test_build_graph_simple_case(service, mock_zotero_gateway, mock_metadata_service):
    mock_zotero_gateway.get_collection_id_by_name.return_value = "COL_ID"
    item_a = create_zotero_item("KEY_A", "Paper A", "10.1/A")
    item_b = create_zotero_item("KEY_B", "Paper B", "10.1/B")
    item_c = create_zotero_item("KEY_C", "Paper C", "10.1/C")

    mock_zotero_gateway.get_items_in_collection.return_value = iter([item_a, item_b, item_c])

    def get_metadata_side_effect(doi):
        if doi == "10.1/A":
            return ResearchPaper(title="A", abstract="", references=["10.1/B", "10.999/external"])
        if doi == "10.1/B":
            return ResearchPaper(title="B", abstract="", references=["10.1/C"])
        return ResearchPaper(title="C", abstract="", references=[])

    mock_metadata_service.get_enriched_metadata.side_effect = get_metadata_side_effect

    graph_dot = service.build_graph(["My Collection"])

    assert "digraph CitationGraph {" in graph_dot
    assert '  "10.1/A" -> "10.1/B";' in graph_dot
    assert '  "10.1/B" -> "10.1/C";' in graph_dot
    assert "10.999/external" not in graph_dot


def test_build_graph_no_references(service, mock_zotero_gateway, mock_metadata_service):
    mock_zotero_gateway.get_collection_id_by_name.return_value = "COL_ID"
    item_a = create_zotero_item("KEY_A", "Paper A", "10.1/A")
    mock_zotero_gateway.get_items_in_collection.return_value = iter([item_a])
    mock_metadata_service.get_enriched_metadata.return_value = ResearchPaper(
        title="A", abstract="", references=[]
    )

    graph_dot = service.build_graph(["My Collection"])

    assert '  "10.1/A" [label="Paper A"];' in graph_dot
    assert "->" not in graph_dot
