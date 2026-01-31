import sys
from unittest.mock import patch

import pytest

from zotero_cli.cli.main import main


@pytest.fixture
def mock_attachment_service():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_attachment_service") as mock_get:
        yield mock_get.return_value


@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv("ZOTERO_API_KEY", "test_key")
    monkeypatch.setenv("ZOTERO_USER_ID", "12345")


def test_collection_pdf_fetch(mock_attachment_service, env_vars, capsys):
    mock_attachment_service.attach_pdfs_to_collection.return_value = [101, 102]

    test_args = ["zotero-cli", "collection", "pdf", "fetch", "--collection", "MyCol"]
    with patch.object(sys, "argv", test_args):
        main()

    out = capsys.readouterr().out
    assert "Enqueued 2 discovery jobs" in out
    mock_attachment_service.attach_pdfs_to_collection.assert_called_with("MyCol")


def test_collection_pdf_fetch_no_jobs(mock_attachment_service, env_vars, capsys):
    mock_attachment_service.attach_pdfs_to_collection.return_value = []

    test_args = ["zotero-cli", "collection", "pdf", "fetch", "--collection", "MyCol"]
    with patch.object(sys, "argv", test_args):
        main()

    out = capsys.readouterr().out
    assert "No items in 'MyCol' missing PDFs" in out
