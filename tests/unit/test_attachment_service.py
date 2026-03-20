from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.attachment_service import AttachmentService
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService
from zotero_cli.core.services.pdf_finder_service import PDFFinderService
from zotero_cli.core.services.purge_service import PurgeService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return Mock(spec=ZoteroGateway)


@pytest.fixture
def mock_aggregator():
    return Mock(spec=MetadataAggregatorService)


@pytest.fixture
def mock_purge_service():
    return MagicMock(spec=PurgeService)


@pytest.fixture
def mock_pdf_finder():
    return MagicMock(spec=PDFFinderService)


@pytest.fixture
def service(mock_gateway, mock_aggregator, mock_purge_service, mock_pdf_finder):
    # Pass mock_gateway for all repo interfaces since it implements them all
    return AttachmentService(
        mock_gateway,
        mock_gateway,
        mock_gateway,
        mock_gateway,
        mock_aggregator,
        mock_purge_service,
        pdf_finder=mock_pdf_finder,
    )


def create_item(key="KEY1", doi="10.1234/test"):
    return ZoteroItem(key=key, version=1, item_type="journalArticle", title="Test Paper", doi=doi)


def test_collection_not_found(service, mock_gateway):
    mock_gateway.get_collection_id_by_name.return_value = None
    result = service.attach_pdfs_to_collection("NonExistent")
    assert result == []
    mock_gateway.get_items_in_collection.assert_not_called()


def test_enqueue_pdf_job(service, mock_gateway, mock_pdf_finder):
    """Test that items without PDFs are enqueued for processing."""
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    item = create_item()
    mock_gateway.get_items_in_collection.return_value = iter([item])
    mock_gateway.get_item.return_value = item

    # No existing PDF
    mock_gateway.get_item_children.return_value = []

    # Mock PDF finder returning a job ID
    mock_pdf_finder.enqueue_find_pdf.return_value = 101

    job_ids = service.attach_pdfs_to_collection("TestCollection")

    assert job_ids == [101]
    mock_pdf_finder.enqueue_find_pdf.assert_called_with("KEY1")


def test_already_has_pdf(service, mock_gateway, mock_pdf_finder):
    """Test that items with existing PDFs are skipped."""
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    item = create_item()
    mock_gateway.get_items_in_collection.return_value = iter([item])

    # Simulate existing PDF attachment
    attachment = {
        "data": {
            "itemType": "attachment",
            "linkMode": "imported_file",
            "contentType": "application/pdf",
        }
    }
    mock_gateway.get_item_children.return_value = [attachment]

    job_ids = service.attach_pdfs_to_collection("TestCollection")

    assert job_ids == []
    mock_pdf_finder.enqueue_find_pdf.assert_not_called()


def test_multiple_items_mixed(service, mock_gateway, mock_pdf_finder):
    """Test a mix of items needing PDF and items already having PDF."""
    mock_gateway.get_collection_id_by_name.return_value = "COL1"

    item1 = create_item(key="KEY1")  # Needs PDF
    item2 = create_item(key="KEY2")  # Has PDF

    mock_gateway.get_items_in_collection.return_value = iter([item1, item2])

    # Mock children responses for the loop
    # Call 1 (KEY1): []
    # Call 2 (KEY2): [attachment]
    attachment = {
        "data": {
            "itemType": "attachment",
            "linkMode": "imported_file",
            "contentType": "application/pdf",
        }
    }
    mock_gateway.get_item_children.side_effect = [[], [attachment]]

    mock_pdf_finder.enqueue_find_pdf.return_value = 202

    job_ids = service.attach_pdfs_to_collection("TestCollection")

    assert job_ids == [202]
    mock_pdf_finder.enqueue_find_pdf.assert_called_once_with("KEY1")


def test_remove_attachments_from_item(service, mock_purge_service):
    mock_purge_service.purge_attachments.return_value = {"deleted": 2, "skipped": 0, "errors": 0}

    count = service.remove_attachments_from_item("KEY1", dry_run=False)

    assert count == 2
    mock_purge_service.purge_attachments.assert_called_once_with(["KEY1"], dry_run=False)


def test_remove_attachments_from_collection(service, mock_gateway, mock_purge_service):
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    item1 = create_item("K1")
    item2 = create_item("K2")
    mock_gateway.get_items_in_collection.return_value = iter([item1, item2])

    mock_purge_service.purge_attachments.return_value = {"deleted": 0, "skipped": 2, "errors": 0}

    count = service.remove_attachments_from_collection("TestCol", dry_run=True)

    assert count == 2
    mock_purge_service.purge_attachments.assert_called_once_with(["K1", "K2"], dry_run=True)


def test_get_fulltext_success(service, mock_gateway):
    item_key = "KEY1"
    attachment_key = "ATT1"
    
    # Mocking children (one PDF)
    mock_gateway.get_item_children.return_value = [{
        "key": attachment_key,
        "data": {"itemType": "attachment", "contentType": "application/pdf"}
    }]
    
    # Mocking successful download
    mock_gateway.download_attachment.return_value = True
    
    # Mocking MarkItDown lib
    with patch("markitdown.MarkItDown") as mock_mid_class:
        mock_mid = mock_mid_class.return_value
        # Mocking the conversion result
        mock_convert_result = MagicMock()
        mock_convert_result.text_content = "# Test Content"
        mock_mid.convert.return_value = mock_convert_result
        
        result = service.get_fulltext(item_key)
        
        assert result == "# Test Content"
        # Since get_fulltext uses tempfile, we check if download_attachment was called
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
    mock_gateway.get_item_children.return_value = [{
        "key": "ATT",
        "data": {"itemType": "attachment", "contentType": "application/pdf"}
    }]
    
    mock_gateway.download_attachment.return_value = True
    
    with patch("markitdown.MarkItDown") as mock_mid_class:
        mock_mid = mock_mid_class.return_value
        mock_convert_result = MagicMock()
        mock_convert_result.text_content = "Content"
        mock_mid.convert.return_value = mock_convert_result
        
        stats = service.bulk_export_markdown(items, tmp_path)
        
        assert stats["total"] == 2
        assert stats["success"] == 2
        
        # Check files created (slugify produces lowercase)
        assert (tmp_path / "K1_test_paper.md").exists()
        assert (tmp_path / "K2_test_paper.md").exists()
