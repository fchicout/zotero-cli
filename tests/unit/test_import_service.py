from unittest.mock import Mock

import pytest

from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.services.collection_service import CollectionService
from zotero_cli.core.services.import_service import ImportService


@pytest.fixture
def mock_item_repo():
    return Mock()


@pytest.fixture
def mock_col_service():
    return Mock(spec=CollectionService)


@pytest.fixture
def import_service(mock_item_repo, mock_col_service):
    return ImportService(mock_item_repo, mock_col_service)


def test_import_papers_success(import_service, mock_item_repo, mock_col_service):
    mock_col_service.get_or_create_collection_id.return_value = "COL123"
    mock_item_repo.create_item.return_value = True

    papers = [
        ResearchPaper(title="Paper 1", abstract=""),
        ResearchPaper(title="Paper 2", abstract=""),
    ]

    count = import_service.import_papers(iter(papers), "My Collection")

    assert count == 2
    mock_col_service.get_or_create_collection_id.assert_called_once_with("My Collection")
    assert mock_item_repo.create_item.call_count == 2


def test_import_papers_partial_failure(import_service, mock_item_repo, mock_col_service):
    mock_col_service.get_or_create_collection_id.return_value = "COL123"
    mock_item_repo.create_item.side_effect = [True, False]

    papers = [ResearchPaper(title="P1", abstract=""), ResearchPaper(title="P2", abstract="")]
    count = import_service.import_papers(iter(papers), "Col")

    assert count == 1


def test_add_manual_paper(import_service, mock_item_repo, mock_col_service):
    mock_col_service.get_or_create_collection_id.return_value = "COL123"
    mock_item_repo.create_item.return_value = True

    paper = ResearchPaper(title="Manual", abstract="")
    success = import_service.add_manual_paper(paper, "Col")

    assert success is True
    mock_item_repo.create_item.assert_called_with(paper, "COL123")
