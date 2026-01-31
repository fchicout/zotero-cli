import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.services.snowball_graph import SnowballGraphService
from zotero_cli.core.services.snowball_ingestion import SnowballIngestionService


@pytest.fixture
def temp_graph_path():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    yield Path(path)
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def graph_service(temp_graph_path):
    return SnowballGraphService(temp_graph_path)


@pytest.fixture
def mock_metadata_service():
    return MagicMock()


@pytest.fixture
def mock_item_repo():
    return MagicMock()


@pytest.fixture
def mock_collection_repo():
    return MagicMock()


@pytest.fixture
def mock_duplicate_finder():
    return MagicMock()


@pytest.fixture
def ingestion_service(
    graph_service,
    mock_metadata_service,
    mock_item_repo,
    mock_collection_repo,
    mock_duplicate_finder,
):
    return SnowballIngestionService(
        graph_service,
        mock_metadata_service,
        mock_item_repo,
        mock_collection_repo,
        mock_duplicate_finder,
    )


def test_ingest_candidates_success(
    ingestion_service, graph_service, mock_item_repo, mock_collection_repo, mock_metadata_service
):
    # Setup graph with an ACCEPTED node
    parent_doi = "10.1001/parent"
    doi = "10.1001/accepted"
    cand = {"doi": doi, "title": "Accepted Paper", "generation": 1}
    graph_service.add_candidate(cand, parent_doi=parent_doi, direction="forward", generation=1)

    # Ensure parent is already marked as IMPORTED so it's not scanned
    graph_service.update_status(parent_doi, SnowballIngestionService.STATUS_IMPORTED)
    # Mark candidate as ACCEPTED for ingestion
    graph_service.update_status(doi, SnowballGraphService.STATUS_ACCEPTED)

    # Mock repos
    mock_collection_repo.get_collection_id_by_name.return_value = "COL123"
    mock_item_repo.get_items_by_doi.return_value = iter([]) # No duplicates

    # Mock hydration
    paper = ResearchPaper(title="Accepted Paper", abstract="Some abstract", doi=doi)
    mock_metadata_service.get_enriched_metadata.return_value = paper

    # Mock create_item
    mock_item_repo.create_item.return_value = True

    # Execute
    stats = ingestion_service.ingest_candidates("Target Collection")

    # Verify
    assert stats["imported"] == 1
    assert graph_service.graph.nodes[doi]["status"] == SnowballIngestionService.STATUS_IMPORTED

    # Verify create_item call and lineage injection
    mock_item_repo.create_item.assert_called_once()
    called_paper = mock_item_repo.create_item.call_args[0][0]
    assert "zotero-cli-snowball-parent: 10.1001/parent" in called_paper.extra
    assert "zotero-cli-snowball-gen: 1" in called_paper.extra


def test_ingest_candidates_duplicate_skipping(
    ingestion_service, graph_service, mock_item_repo, mock_collection_repo
):
    doi = "10.1001/duplicate"
    graph_service.add_candidate({"doi": doi, "title": "Duplicate Paper"})
    graph_service.update_status(doi, SnowballGraphService.STATUS_ACCEPTED)

    mock_collection_repo.get_collection_id_by_name.return_value = "COL123"

    # Mock item exists in library
    from zotero_cli.core.zotero_item import ZoteroItem
    existing_item = ZoteroItem(key="EXIST", version=1, item_type="journalArticle", doi=doi)
    mock_item_repo.get_items_by_doi.return_value = iter([existing_item])

    stats = ingestion_service.ingest_candidates("Target Collection")

    assert stats["imported"] == 0
    assert stats["duplicates"] == 1
    assert graph_service.graph.nodes[doi]["status"] == SnowballIngestionService.STATUS_IMPORTED
    mock_item_repo.create_item.assert_not_called()
