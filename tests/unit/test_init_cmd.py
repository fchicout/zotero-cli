import sys
from unittest.mock import Mock, patch

import pytest
from zotero_cli.cli.main import main


def test_init_command_success(tmp_path, capsys):
    config_file = tmp_path / "config.toml"

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


def test_init_command_user_library_path(tmp_path, capsys):
    config_file = tmp_path / "config.toml"

    # api_key, lib_type, lib_id, ss_key, up_email
    # Note: user_id and target_group should be skipped for 'user' type in current implementation
    # Actually, current implementation asks for user_id/target_group ONLY if lib_type == 'group'
    inputs = ["user_key", "user", "my_user_id", "ss_val", "up_val"]

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

    content = config_file.read_text()
    assert 'library_type = "user"' in content
    assert 'library_id = "my_user_id"' in content
    assert "user_id =" not in content  # Not prompted for 'user' type
    assert "target_group =" not in content


def test_init_command_verification_failure_save_anyway(tmp_path, capsys):
    config_file = tmp_path / "config.toml"

    # api_key, lib_type, lib_id, ss_key, up_email
    inputs = ["invalid_key", "user", "123", "", ""]

    with (
        patch("rich.prompt.Prompt.ask", side_effect=inputs),
        patch("rich.prompt.Confirm.ask", return_value=True),  # Save anyway? -> Yes
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_gw_get,
    ):
        mock_gw = mock_gw_get.return_value
        mock_gw.http.get.side_effect = Exception("Unauthorized")

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
        patch("rich.prompt.Confirm.ask", side_effect=[True, True]),  # Overwrite? -> Yes, Verify? -> Yes
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_gw_get,
    ):
        mock_gw = mock_gw_get.return_value
        mock_gw.http.get.return_value = Mock()

        test_args = ["zotero-cli", "--config", str(config_file), "init"]
        with patch.object(sys, "argv", test_args):
            main()

    assert "Configuration saved to" in capsys.readouterr().out
    assert 'api_key = "new_key"' in config_file.read_text()


def test_init_command_write_error(tmp_path, capsys):


    config_file = tmp_path / "config.toml"





    inputs = ["key", "user", "123", "", ""]





    with (


        patch("rich.prompt.Prompt.ask", side_effect=inputs),


        patch("rich.prompt.Confirm.ask", return_value=True),


        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_gw_get,


    ):


        mock_gw = mock_gw_get.return_value


        mock_gw.http.get.return_value = Mock()





        # Mock open to raise IOError


        with patch("builtins.open", side_effect=IOError("Permission denied")):


            test_args = ["zotero-cli", "--config", str(config_file), "init"]


            with patch.object(sys, "argv", test_args):


                with pytest.raises(SystemExit):


                    main()





    captured = capsys.readouterr()


    assert "Failed to save config: Permission denied" in captured.out

