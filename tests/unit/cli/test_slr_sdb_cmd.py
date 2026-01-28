import sys
from unittest.mock import MagicMock, patch
import pytest
from zotero_cli.cli.main import main

@pytest.fixture
def mock_gateway():
    return MagicMock()

@pytest.fixture
def mock_sdb_service():
    with patch("zotero_cli.core.services.sdb.sdb_service.SDBService") as mock_cls:
        mock_instance = mock_cls.return_value
        yield mock_instance

def test_slr_sdb_inspect(mock_gateway, mock_sdb_service, capsys):
    mock_sdb_service.inspect_item_sdb.return_value = [
        {"decision": "accepted", "reason_code": ["C1"], "persona": "P1", "phase": "ph1"}
    ]
    
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=mock_gateway):
        test_args = ["zotero-cli", "slr", "sdb", "inspect", "KEY1"]
        with patch.object(sys, "argv", test_args):
            main()
            
    mock_sdb_service.inspect_item_sdb.assert_called_with("KEY1")
    mock_sdb_service.build_inspect_table.assert_called_once()

def test_slr_sdb_edit_dry_run(mock_gateway, mock_sdb_service, capsys):
    mock_sdb_service.edit_sdb_entry.return_value = (True, "Would update")
    
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=mock_gateway):
        test_args = [
            "zotero-cli", "slr", "sdb", "edit", "KEY1", 
            "--persona", "P1", "--phase", "ph1", 
            "--set-decision", "rejected"
        ]
        with patch.object(sys, "argv", test_args):
            main()
            
    # Verify service call with dry_run=True (default)
    mock_sdb_service.edit_sdb_entry.assert_called_with(
        "KEY1", "P1", "ph1", {"decision": "rejected"}, dry_run=True
    )
    assert "Would update" in capsys.readouterr().out

def test_slr_sdb_upgrade(mock_gateway, mock_sdb_service, capsys):
    mock_sdb_service.upgrade_sdb_entries.return_value = {"scanned": 1, "upgraded": 1, "skipped": 0, "errors": 0}
    
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=mock_gateway):
        test_args = ["zotero-cli", "slr", "sdb", "upgrade", "--collection", "Col1", "--execute"]
        with patch.object(sys, "argv", test_args):
            main()
            
    mock_sdb_service.upgrade_sdb_entries.assert_called_with("Col1", dry_run=False)
    assert "Upgraded: 1" in capsys.readouterr().out
