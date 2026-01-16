import pytest
from unittest.mock import patch, Mock
import sys
from zotero_cli.cli.main import main

@pytest.fixture(autouse=True)
def mock_config(tmp_path):
    dummy_path = tmp_path / "dummy_config.toml"
    with patch('zotero_cli.core.config.ConfigLoader._get_default_config_path', return_value=dummy_path):
        yield

def test_modern_review_decide_invocation(capsys):
    with patch('zotero_cli.cli.commands.screen_cmd.ScreeningService') as mock_service_cls:
        with patch('zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway'):
            mock_service = mock_service_cls.return_value
            mock_service.record_decision.return_value = True

            # Modern path
            test_args = ['zotero-cli', 'review', 'decide', '--key', 'K1', '--vote', 'INCLUDE', '--code', 'TEST']
            with patch.object(sys, 'argv', test_args):
                main()
            
            mock_service.record_decision.assert_called_once()
            assert "[DEPRECATED]" not in capsys.readouterr().err

def test_legacy_decide_routing(capsys):
    with patch('zotero_cli.cli.commands.screen_cmd.ScreeningService') as mock_service_cls:
        with patch('zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway'):
            mock_service = mock_service_cls.return_value
            mock_service.record_decision.return_value = True

            # Legacy path
            test_args = ['zotero-cli', 'decide', '--key', 'K1', '--vote', 'INCLUDE', '--code', 'TEST']
            with patch.object(sys, 'argv', test_args):
                main()
            
            mock_service.record_decision.assert_called_once()
            assert "[DEPRECATED] 'decide' is now 'zotero-cli review decide'" in capsys.readouterr().err

def test_legacy_manage_move_routing(capsys):
    with patch('zotero_cli.cli.commands.item_cmd.CollectionService') as mock_service_cls:
        with patch('zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway'):
            mock_service = mock_service_cls.return_value
            mock_service.move_item.return_value = True

            # Legacy path
            test_args = ['zotero-cli', 'manage', 'move', '--item-id', 'I', '--source', 'S', '--target', 'T']
            with patch.object(sys, 'argv', test_args):
                main()
            
            mock_service.move_item.assert_called_once()
            assert "[DEPRECATED] 'manage move' is now 'item move'" in capsys.readouterr().err
