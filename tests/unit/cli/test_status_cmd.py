import argparse
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.cli.commands.slr.status_cmd import StatusCommand


@pytest.fixture
def mock_deps():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mw:
        yield mw.return_value

def test_status_command_execute(mock_deps, capsys):
    # Setup
    mock_status = MagicMock()
    mock_status.source_name = "raw_test"
    mock_status.source_key = "K1"
    mock_status.total_in_root = 10
    mock_status.total_unique = 15
    mock_status.phases = {}

    with patch("zotero_cli.core.services.slr.status_service.SLRStatusService.get_slr_status", return_value=[mock_status]):
        args = argparse.Namespace(verb="status")
        StatusCommand.execute(args)

        out = capsys.readouterr().out
        assert "SLR Progress Status" in out
        assert "raw_test" in out
        assert "15" in out # Tree Total

def test_status_command_no_collections(mock_deps, capsys):
    with patch("zotero_cli.core.services.slr.status_service.SLRStatusService.get_slr_status", return_value=[]):
        args = argparse.Namespace(verb="status")
        StatusCommand.execute(args)

        out = capsys.readouterr().out
        assert "No raw_* collections found" in out
