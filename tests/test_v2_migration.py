import sys
from unittest.mock import patch

import pytest

from zotero_cli.cli.main import main


@pytest.fixture(autouse=True)
def mock_config(tmp_path):
    dummy_path = tmp_path / "dummy_config.toml"
    with patch('zotero_cli.core.config.ConfigLoader._get_default_config_path', return_value=dummy_path):
        yield

def test_modern_review_decide_invocation(capsys):
    with patch('zotero_cli.infra.factory.GatewayFactory.get_screening_service') as mock_factory_get:
        mock_service = mock_factory_get.return_value
        mock_service.record_decision.return_value = True

        # Modern path
        test_args = ['zotero-cli', 'review', 'decide', '--key', 'K1', '--vote', 'INCLUDE', '--code', 'TEST']
        with patch.object(sys, 'argv', test_args):
            main()

        mock_service.record_decision.assert_called_once()
        assert "[DEPRECATED]" not in capsys.readouterr().err
