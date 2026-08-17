import sys
from unittest.mock import patch

from zotero_cli.cli.main import main
from zotero_cli.core.models import KeyIdentity


def test_init_command_basic(tmp_path, capsys):
    config_file = tmp_path / "config.toml"

    # api_key, lib_type, lib_id, user_id, target_group, ss_key, up_email
    inputs = ["test_api_key", "group", "12345", "67890", "my-group", "ss_key", "up@email.com"]

    with (
        patch("rich.prompt.Prompt.ask", side_effect=inputs),
        patch(
            "zotero_cli.cli.commands.init_cmd.ZoteroAPIClient.resolve_key_identity",
            side_effect=Exception("mocked: no network in unit tests"),
        ),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_gw_get,
    ):
        mock_gw = mock_gw_get.return_value
        # Mock verify_credentials to return True
        mock_gw.verify_credentials.return_value = True

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


def test_init_command_resolves_identity_and_prefills_user_library_id(tmp_path, capsys):
    config_file = tmp_path / "config.toml"

    # api_key, lib_type, lib_id, ss_key, up_email
    inputs = ["test_api_key", "user", "999", "ss_key", ""]

    with (
        patch("rich.prompt.Prompt.ask", side_effect=inputs) as mock_prompt,
        patch(
            "zotero_cli.cli.commands.init_cmd.ZoteroAPIClient.resolve_key_identity",
            return_value=KeyIdentity(user_id=999, username="janedoe", access={}),
        ),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_gw_get,
    ):
        mock_gw = mock_gw_get.return_value
        mock_gw.verify_credentials.return_value = True

        test_args = ["zotero-cli", "--config", str(config_file), "init"]
        with patch.object(sys, "argv", test_args):
            main()

    out = capsys.readouterr().out
    assert "Key belongs to 'janedoe' (User ID: 999)" in out

    lib_id_call = next(
        c for c in mock_prompt.call_args_list if c.args and c.args[0].startswith("Library ID")
    )
    assert lib_id_call.kwargs.get("default") == "999"

    content = config_file.read_text()
    assert 'library_id = "999"' in content


def test_init_command_identity_resolution_failure_warns_and_continues(tmp_path, capsys):
    config_file = tmp_path / "config.toml"

    # api_key, lib_type, lib_id, user_id, target_group, ss_key, up_email
    inputs = ["test_api_key", "group", "12345", "", "", "", ""]

    with (
        patch("rich.prompt.Prompt.ask", side_effect=inputs),
        patch(
            "zotero_cli.cli.commands.init_cmd.ZoteroAPIClient.resolve_key_identity",
            side_effect=Exception("invalid key"),
        ),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_gw_get,
    ):
        mock_gw = mock_gw_get.return_value
        mock_gw.verify_credentials.return_value = True

        test_args = ["zotero-cli", "--config", str(config_file), "init"]
        with patch.object(sys, "argv", test_args):
            main()

    out = capsys.readouterr().out
    assert "Could not resolve key identity yet" in out
    assert config_file.exists()


def test_init_command_user_library(tmp_path, capsys):
    config_file = tmp_path / "config.toml"

    # api_key, lib_type, lib_id, ss_key, up_email
    # Note: user_id and target_group should be skipped for 'user' type in current implementation
    inputs = ["user_key", "user", "my_uid", "ss_key", ""]

    with (
        patch("rich.prompt.Prompt.ask", side_effect=inputs),
        patch(
            "zotero_cli.cli.commands.init_cmd.ZoteroAPIClient.resolve_key_identity",
            side_effect=Exception("mocked: no network in unit tests"),
        ),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_gw_get,
    ):
        mock_gw = mock_gw_get.return_value
        mock_gw.verify_credentials.return_value = True

        test_args = ["zotero-cli", "--config", str(config_file), "init"]
        with patch.object(sys, "argv", test_args):
            main()

    content = config_file.read_text()
    assert 'library_type = "user"' in content
    assert 'library_id = "my_uid"' in content
    assert "user_id =" not in content
    assert "target_group =" not in content


def test_init_command_verification_failure_save_anyway(tmp_path, capsys):
    config_file = tmp_path / "config.toml"

    # api_key, lib_type, lib_id, ss_key, up_email
    inputs = ["invalid_key", "user", "123", "", ""]

    with (
        patch("rich.prompt.Prompt.ask", side_effect=inputs),
        patch("rich.prompt.Confirm.ask", return_value=True),  # Save anyway? -> Yes
        patch(
            "zotero_cli.cli.commands.init_cmd.ZoteroAPIClient.resolve_key_identity",
            side_effect=Exception("mocked: no network in unit tests"),
        ),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_gw_get,
    ):
        mock_gw = mock_gw_get.return_value
        mock_gw.verify_credentials.return_value = False

        test_args = ["zotero-cli", "--config", str(config_file), "init"]
        with patch.object(sys, "argv", test_args):
            main()

    captured = capsys.readouterr()
    assert "Verification failed" in captured.out
    assert "Configuration saved to" in captured.out
    assert config_file.exists()


def test_init_command_overwrite_existing(tmp_path, capsys):
    config_file = tmp_path / "config.toml"
    config_file.write_text("old content")

    # api_key, lib_type, lib_id, ss_key, up_email
    inputs = ["new_key", "user", "456", "", ""]

    with (
        patch("rich.prompt.Prompt.ask", side_effect=inputs),
        patch("rich.prompt.Confirm.ask", return_value=True),  # Overwrite? -> Yes
        patch(
            "zotero_cli.cli.commands.init_cmd.ZoteroAPIClient.resolve_key_identity",
            side_effect=Exception("mocked: no network in unit tests"),
        ),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_gw_get,
    ):
        mock_gw = mock_gw_get.return_value
        mock_gw.verify_credentials.return_value = True

        test_args = ["zotero-cli", "--config", str(config_file), "init"]
        with patch.object(sys, "argv", test_args):
            main()

    content = config_file.read_text()
    assert 'api_key = "new_key"' in content
    assert 'library_id = "456"' in content


def test_init_command_abort_overwrite(tmp_path, capsys):
    config_file = tmp_path / "config.toml"
    config_file.write_text("should remain")

    with (
        patch("rich.prompt.Confirm.ask", return_value=False),  # Overwrite? -> No
    ):
        test_args = ["zotero-cli", "--config", str(config_file), "init"]
        with patch.object(sys, "argv", test_args):
            main()

    assert config_file.read_text() == "should remain"
    assert "Aborted" in capsys.readouterr().out
