from unittest.mock import MagicMock

import pytest

from zotero_cli.core.models import ScreeningStatus, SearchResult, VerifiedSearchResult


@pytest.mark.unit
def test_verified_search_result_model():
    res = VerifiedSearchResult(
        item_key="KEY1",
        text="Sample text",
        score=0.9,
        metadata={"author": "John Doe"},
        is_verified=True,
        verification_errors=[],
        screening_status=ScreeningStatus.ACCEPTED,
        citation_key="Doe2024"
    )
    assert res.item_key == "KEY1"
    assert res.is_verified is True
    assert res.screening_status == ScreeningStatus.ACCEPTED

@pytest.mark.unit
def test_rag_service_verify_results_interface():
    mock_vector_repo = MagicMock()
    mock_embedding_provider = MagicMock()
    mock_gateway = MagicMock()

    from zotero_cli.core.zotero_item import ZoteroItem
    mock_item = ZoteroItem.from_raw_zotero_item({
        "key": "KEY1",
        "data": {"key": "KEY1", "version": 1, "itemType": "journalArticle", "title": "Test", "DOI": "10.1000/1"}
    })
    mock_gateway.get_item.return_value = mock_item
    mock_gateway.get_item_children.return_value = []

    mock_attachment_service = MagicMock()

    from zotero_cli.core.services.rag_service import RAGServiceBase
    service = RAGServiceBase(mock_gateway, mock_vector_repo, mock_embedding_provider, mock_attachment_service)

    results = [
        SearchResult(item_key="KEY1", text="text1", score=0.8, metadata={})
    ]

    verified = service.verify_results(results)
    assert len(verified) == 1
    assert isinstance(verified[0], VerifiedSearchResult)

@pytest.mark.unit
def test_rag_service_verify_logic():
    mock_gateway = MagicMock()
    mock_vector_repo = MagicMock()
    mock_embedding_provider = MagicMock()
    mock_attachment_service = MagicMock()

    from zotero_cli.core.services.rag_service import RAGServiceBase
    from zotero_cli.core.zotero_item import ZoteroItem

    service = RAGServiceBase(mock_gateway, mock_vector_repo, mock_embedding_provider, mock_attachment_service)

    # Use real ZoteroItem objects to avoid mock fragility
    item1 = ZoteroItem.from_raw_zotero_item({
        "key": "KEY1",
        "data": {
            "key": "KEY1",
            "version": 1,
            "itemType": "journalArticle",
            "title": "Verified Paper",
            "abstractNote": "Some abstract",
            "DOI": "10.1000/1",
            "tags": [{"tag": "rsl:include"}],
            "extra": "Citation Key: Key2024",
            "creators": [],
            "date": "2024"
        }
    })

    item2 = ZoteroItem.from_raw_zotero_item({
        "key": "KEY2",
        "data": {
            "key": "KEY2",
            "version": 1,
            "itemType": "journalArticle",
            "title": "Unverified Paper",
            "abstractNote": "Abstract",
            "tags": [],
            "extra": "",
            "creators": [],
            "date": "2024"
        }
    })

    mock_gateway.get_item.side_effect = lambda k: item1 if k == "KEY1" else (item2 if k == "KEY2" else None)
    mock_gateway.get_item_children.return_value = []

    results = [
        SearchResult(item_key="KEY1", text="text1", score=0.9, metadata={}),
        SearchResult(item_key="KEY2", text="text2", score=0.8, metadata={})
    ]

    verified = service.verify_results(results)

    assert len(verified) == 2
    assert verified[0].is_verified is True
    assert verified[0].citation_key == "Key2024"
    assert verified[0].screening_status == ScreeningStatus.ACCEPTED

    assert verified[1].is_verified is False
    assert "Missing DOI or arXiv ID" in verified[1].verification_errors
    assert verified[1].screening_status == ScreeningStatus.UNKNOWN
