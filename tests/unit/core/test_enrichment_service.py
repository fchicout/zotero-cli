from unittest.mock import Mock

import pytest

from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.services.enrichment_service import EnrichmentService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return Mock()


@pytest.fixture
def service(mock_gateway):
    return EnrichmentService(mock_gateway, mock_gateway, mock_gateway)


def test_hydrate_item_no_doi_to_doi(service, mock_gateway):
    # Setup
    item_key = "ITEM1"
    item = ZoteroItem(
        key=item_key,
        version=1,
        item_type="journalArticle",
        arxiv_id="2103.10433",
        doi=None,
        title="ArXiv Title",
        raw_data={"data": {"libraryCatalog": "arXiv.org"}},
    )
    mock_gateway.get_item.return_value = item

    latest_paper = ResearchPaper(
        title="ArXiv Title", abstract="...", doi="10.1145/3442188.3445922", publication="Nature"
    )
    mock_gateway.search.return_value = iter([latest_paper])
    mock_gateway.update_item.return_value = True

    # Execute
    report = service.hydrate_item(item_key)

    # Assert
    assert report is not None
    assert report["new_doi"] == "10.1145/3442188.3445922"
    assert report["new_journal"] == "Nature"
    mock_gateway.update_item.assert_called_once_with(
        item_key, 1, {"DOI": "10.1145/3442188.3445922", "publicationTitle": "Nature"}
    )


def test_hydrate_item_dry_run(service, mock_gateway):
    # Setup
    item_key = "ITEM1"
    item = ZoteroItem(
        key=item_key,
        version=1,
        item_type="journalArticle",
        arxiv_id="2103.10433",
        doi=None,
        title="ArXiv Title",
        raw_data={"data": {"libraryCatalog": "arXiv.org"}},
    )
    mock_gateway.get_item.return_value = item

    latest_paper = ResearchPaper(
        title="ArXiv Title", abstract="...", doi="10.1145/3442188.3445922", publication="Nature"
    )
    mock_gateway.search.return_value = iter([latest_paper])

    # Execute
    report = service.hydrate_item(item_key, dry_run=True)

    # Assert
    assert report is not None
    mock_gateway.update_item.assert_not_called()


def test_hydrate_item_no_changes(service, mock_gateway):
    # Setup
    item_key = "ITEM1"
    item = ZoteroItem(
        key=item_key,
        version=1,
        item_type="journalArticle",
        arxiv_id="2103.10433",
        doi="10.1145/3442188.3445922",
        title="ArXiv Title",
        raw_data={"data": {"libraryCatalog": "arXiv.org", "publicationTitle": "Nature"}},
    )
    mock_gateway.get_item.return_value = item

    latest_paper = ResearchPaper(
        title="ArXiv Title", abstract="...", doi="10.1145/3442188.3445922", publication="Nature"
    )
    mock_gateway.search.return_value = iter([latest_paper])

    # Execute
    report = service.hydrate_item(item_key)

    # Assert
    assert report is None
    mock_gateway.update_item.assert_not_called()


def test_hydrate_collection(service, mock_gateway):
    # Setup
    col_id = "COL1"
    item1 = ZoteroItem(key="K1", version=1, item_type="art", arxiv_id="123", doi=None, raw_data={})
    item2 = ZoteroItem(
        key="K2", version=1, item_type="art", arxiv_id="456", doi="exists", raw_data={}
    )

    mock_gateway.get_items_in_collection.return_value = iter([item1, item2])

    # Paper for K1 (has new DOI)
    p1 = ResearchPaper(title="T1", abstract=".", doi="DOI1", publication="J1")
    # Paper for K2 (matches existing)
    p2 = ResearchPaper(title="T2", abstract=".", doi="exists", publication=None)

    def mock_search(q, max_results=1):
        if "123" in q:
            return iter([p1])
        if "456" in q:
            return iter([p2])
        return iter([])

    mock_gateway.search.side_effect = mock_search
    mock_gateway.update_item.return_value = True

    # Execute
    results = service.hydrate_collection(col_id)

    # Assert
    assert len(results) == 1
    assert results[0]["key"] == "K1"
    mock_gateway.update_item.assert_called_once()


def test_hydrate_all(service, mock_gateway):
    # Setup
    item = ZoteroItem(key="K1", version=1, item_type="art", arxiv_id="123", doi=None, raw_data={})

    # Mock global search support
    mock_gateway.search_items.return_value = iter([item])

    p = ResearchPaper(title="T1", abstract=".", doi="DOI1", publication="J1")
    mock_gateway.search.return_value = iter([p])
    mock_gateway.update_item.return_value = True

    # Execute
    results = service.hydrate_all()

    # Assert
    assert len(results) == 1
    assert results[0]["key"] == "K1"
    mock_gateway.search_items.assert_called_once()


def test_is_arxiv_item_detection(service):
    # catalog detection
    item1 = ZoteroItem(
        key="K", version=1, item_type="art", raw_data={"data": {"libraryCatalog": "arXiv.org"}}
    )
    assert service._is_arxiv_item(item1) is True

    # URL detection
    item2 = ZoteroItem(
        key="K", version=1, item_type="art", url="https://arxiv.org/abs/123", raw_data={}
    )
    assert service._is_arxiv_item(item2) is True

    # ArXiv ID detection
    item3 = ZoteroItem(key="K", version=1, item_type="art", arxiv_id="123.456", raw_data={})
    assert service._is_arxiv_item(item3) is True

    # Negative case
    item4 = ZoteroItem(
        key="K", version=1, item_type="art", raw_data={"data": {"libraryCatalog": "IEEE"}}
    )
    assert service._is_arxiv_item(item4) is False
