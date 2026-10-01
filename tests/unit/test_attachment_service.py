from unittest.mock import Mock

import pytest

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.attachment_service import AttachmentService
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService
from zotero_cli.core.services.selftest import SAMPLE_PDF, SAMPLE_PDF_TEXT
from zotero_cli.core.zotero_item import ZoteroItem


def _write_sample_pdf(_attachment_key, path):
    with open(path, "wb") as f:
        f.write(SAMPLE_PDF)
    return True


@pytest.fixture
def mock_gateway():
    return Mock(spec=ZoteroGateway)


@pytest.fixture
def mock_aggregator():
    return Mock(spec=MetadataAggregatorService)


@pytest.fixture
def service(mock_gateway, mock_aggregator):
    # Pass mock_gateway for all repo interfaces since it implements them all
    return AttachmentService(
        mock_gateway,
        mock_gateway,
        mock_gateway,
        mock_gateway,
        mock_aggregator,
    )


def create_item(key="KEY1", doi="10.1234/test"):
    return ZoteroItem(key=key, version=1, item_type="journalArticle", title="Test Paper", doi=doi)


def test_get_fulltext_success(service, mock_gateway):
    item_key = "KEY1"
    attachment_key = "ATT1"

    # Mocking children (one PDF)
    mock_gateway.get_item_children.return_value = [
        {
            "key": attachment_key,
            "data": {"itemType": "attachment", "contentType": "application/pdf"},
        }
    ]

    # A real PDF "downloaded" into the temp path: no mocked converter, so a
    # missing PDF backend fails here (Issue #403).
    mock_gateway.download_attachment.side_effect = _write_sample_pdf

    result = service.get_fulltext(item_key)

    assert result is not None
    assert SAMPLE_PDF_TEXT in result
    mock_gateway.download_attachment.assert_called_once()


def test_get_fulltext_no_pdf(service, mock_gateway):
    # No PDF in children
    mock_gateway.get_item_children.return_value = []
    result = service.get_fulltext("KEY1")
    assert result is None


def test_bulk_export_markdown(service, mock_gateway, tmp_path):
    # Setup two items
    item1 = create_item("K1", doi="10.1/1")
    item2 = create_item("K2", doi="10.1/2")
    items = [item1, item2]

    # All items have PDFs
    mock_gateway.get_item_children.return_value = [
        {"key": "ATT", "data": {"itemType": "attachment", "contentType": "application/pdf"}}
    ]

    mock_gateway.download_attachment.side_effect = _write_sample_pdf

    stats = service.bulk_export_markdown(items, tmp_path)

    assert stats["total"] == 2
    assert stats["success"] == 2

    # Check files created (slugify produces lowercase)
    assert SAMPLE_PDF_TEXT in (tmp_path / "K1_test_paper.md").read_text()
    assert (tmp_path / "K2_test_paper.md").exists()


def test_get_fulltext_returns_none_for_a_corrupt_pdf(service, mock_gateway):
    mock_gateway.get_item_children.return_value = [
        {"key": "ATT", "data": {"itemType": "attachment", "contentType": "application/pdf"}}
    ]

    def write_garbage(_key, path):
        with open(path, "wb") as f:
            f.write(b"not a pdf")
        return True

    mock_gateway.download_attachment.side_effect = write_garbage

    assert service.get_fulltext("K1") is None
