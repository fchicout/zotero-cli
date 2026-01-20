import sys
from unittest.mock import Mock, patch

from zotero_cli.cli.main import main


def test_init_command_success(tmp_path, capsys):
    config_file = tmp_path / "config.toml"

    # Mocking inputs for Prompt.ask and Confirm.ask
    # api_key, lib_type, lib_id, user_id, target_group, ss_key, up_email
    inputs = ["test_api_key", "group", "12345", "67890", "my-group", "ss_key", "up@email.com"]

    with (
        patch("rich.prompt.Prompt.ask", side_effect=inputs),
        patch("rich.prompt.Confirm.ask", return_value=True),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_gw_get,
    ):
        mock_gw = mock_gw_get.return_value
        mock_gw.http.get.return_value = Mock()

        test_args = ["zotero-cli", "--config", str(config_file), "init"]
        with patch.object(sys, "argv", test_args):
            main()

    captured = capsys.readouterr()
    assert "Configuration saved to" in captured.out
    assert config_file.exists()
    content = config_file.read_text()
    assert 'api_key = "test_api_key"' in content
    assert 'library_id = "12345"' in content
    assert 'library_type = "group"' in content
    assert 'user_id = "67890"' in content
    assert 'target_group = "my-group"' in content
    assert 'semantic_scholar_api_key = "ss_key"' in content
    assert 'unpaywall_email = "up@email.com"' in content


def test_init_command_verification_failure_abort(tmp_path, capsys):
    config_file = tmp_path / "config.toml"

    # api_key, lib_type, lib_id, user_id, target_group, ss_key, up_email
    inputs = ["bad_key", "group", "12345", "", "", "", ""]

    with (
        patch("rich.prompt.Prompt.ask", side_effect=inputs),
        patch("rich.prompt.Confirm.ask", return_value=False),  # "Do you want to save anyway?" -> No
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_gw_get,
    ):
        mock_gw = mock_gw_get.return_value
        mock_gw.http.get.side_effect = Exception("Unauthorized")

        test_args = ["zotero-cli", "--config", str(config_file), "init"]
        with patch.object(sys, "argv", test_args):
            main()

    captured = capsys.readouterr()
    assert "Verification failed" in captured.out
    assert "Aborted" in captured.out
    assert not config_file.exists()


def test_init_command_exists_no_force(tmp_path, capsys):
    config_file = tmp_path / "config.toml"
    config_file.write_text("existing content")

    with patch("rich.prompt.Confirm.ask", return_value=False):
        test_args = ["zotero-cli", "--config", str(config_file), "init"]
        with patch.object(sys, "argv", test_args):
            main()

    captured = capsys.readouterr()
    assert "Config file already exists" in captured.out
    assert "Aborted" in captured.out
    assert config_file.read_text() == "existing content"
