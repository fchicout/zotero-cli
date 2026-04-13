import sys
from unittest.mock import patch

import pytest

from zotero_cli.cli.main import main


@pytest.fixture
def mock_screen_service():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_screening_service") as mock_get:
        yield mock_get.return_value


@pytest.fixture
def mock_gateway():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_get:
        yield mock_get.return_value


@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv("ZOTERO_API_KEY", "test_key")
    monkeypatch.setenv("ZOTERO_USER_ID", "12345")


def test_slr_screen_aliases(mock_screen_service, mock_gateway, env_vars):
    # Mock collection resolution
    mock_gateway.get_collection_id_by_name.return_value = "COL123"
    # Mock items return
    mock_screen_service.get_pending_items.return_value = [] # Just to avoid TUI launch for now if no items

    # Verification Request from Issue #96:
    # zotero-cli slr screen --source <COL> --include <INC> --exclude <EXC>
    test_args = [
        "zotero-cli", "slr", "screen",
        "--source", "MySourceCol",
        "--include", "MyIncCol",
        "--exclude", "MyExcCol"
    ]

    with patch("zotero_cli.cli.tui.factory.TUIFactory.get_screening_tui") as mock_tui_factory:
        with patch.object(sys, "argv", test_args):
            # We expect it to NOT throw "unrecognized arguments: --source"
            # It might print "No pending items found" because we returned []
            main()

        # Check if collection was resolved using the alias value
        mock_gateway.get_collection_id_by_name.assert_called_with("MySourceCol")
