from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.core.interfaces import EmbeddingProvider, VectorRepository, ZoteroGateway
from zotero_cli.core.services.rag_service import RAGServiceBase
from zotero_cli.core.services.slr.status_service import DecidedItem


@pytest.fixture
def mock_deps():
    gateway = MagicMock(spec=ZoteroGateway)
    vector_repo = MagicMock(spec=VectorRepository)
    embedding_provider = MagicMock(spec=EmbeddingProvider)
    attachment_service = MagicMock()
    orchestrator = MagicMock()
    citation_service = MagicMock()
    return (
        gateway,
        vector_repo,
        embedding_provider,
        attachment_service,
        orchestrator,
        citation_service,
    )


@pytest.mark.unit
def test_rag_ingest_qa_approved_all(mock_deps):
    (
        gateway,
        vector_repo,
        embedding_provider,
        attachment_service,
        orchestrator,
        citation_service,
    ) = mock_deps

    item1 = MagicMock()
    item1.key = "KEY1"
    item1.extra = ""
    item1.date = "2026"
    item1.creators = []
    item1.title = "QA Paper 1"

    item2 = MagicMock()
    item2.key = "KEY2"
    item2.extra = ""
    item2.date = "2026"
    item2.creators = []
    item2.title = "QA Paper 2"

    gateway.get_item.side_effect = lambda k: (
        item1 if k == "KEY1" else (item2 if k == "KEY2" else None)
    )
    attachment_service.get_fulltext.return_value = "text"
    embedding_provider.embed_batch.return_value = [[0.1]]

    # Mock SLRStatusService decided items
    mock_decided_items = [
        DecidedItem(
            item_key="KEY1",
            title="QA Paper 1",
            source_collection="raw_ieee",
            phase="quality_assessment",
            decision="accepted",
            reason="Score: 3.0",
        ),
        DecidedItem(
            item_key="KEY2",
            title="QA Paper 2",
            source_collection="raw_springer",
            phase="quality_assessment",
            decision="accepted",
            reason="Score: 3.5",
        ),
    ]

    service = RAGServiceBase(
        gateway, vector_repo, embedding_provider, attachment_service, orchestrator, citation_service
    )

    with patch("zotero_cli.core.services.slr.status_service.SLRStatusService") as MockStatusService:
        mock_instance = MockStatusService.return_value
        mock_instance.get_decided_items.return_value = mock_decided_items

        result = service.ingest(qa_approved_only=True)

        assert result["processed"] == 2
        mock_instance.get_decided_items.assert_called_once_with(
            decision_type="accepted", root_key=None, phase_filter="quality_assessment"
        )


@pytest.mark.unit
def test_rag_ingest_qa_approved_filtered(mock_deps):
    (
        gateway,
        vector_repo,
        embedding_provider,
        attachment_service,
        orchestrator,
        citation_service,
    ) = mock_deps

    item1 = MagicMock()
    item1.key = "KEY1"
    item1.extra = ""
    item1.date = "2026"
    item1.creators = []
    item1.title = "QA Paper 1"

    gateway.get_item.side_effect = lambda k: item1 if k == "KEY1" else None
    attachment_service.get_fulltext.return_value = "text"
    embedding_provider.embed_batch.return_value = [[0.1]]

    mock_decided_items = [
        DecidedItem(
            item_key="KEY1",
            title="QA Paper 1",
            source_collection="raw_ieee",
            phase="quality_assessment",
            decision="accepted",
            reason="Score: 3.0",
        ),
    ]

    service = RAGServiceBase(
        gateway, vector_repo, embedding_provider, attachment_service, orchestrator, citation_service
    )

    with patch("zotero_cli.core.services.slr.status_service.SLRStatusService") as MockStatusService:
        mock_instance = MockStatusService.return_value
        mock_instance.get_decided_items.return_value = mock_decided_items

        result = service.ingest(qa_approved_only=True, tree_filter="raw_ieee")

        assert result["processed"] == 1
        mock_instance.get_decided_items.assert_called_once_with(
            decision_type="accepted", root_key="raw_ieee", phase_filter="quality_assessment"
        )
