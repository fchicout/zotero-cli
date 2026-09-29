import os
import stat
import sys
from unittest.mock import patch

from zotero_cli.cli.main import main
from zotero_cli.core.models import KeyIdentity


def test_init_command_basic(tmp_path, capsys):
    config_file = tmp_path / "config.toml"

    # api_key, lib_type, group id, user_id, ss_key, up_email, database_path
    inputs = ["test_api_key", "group", "12345", "67890", "ss_key", "up@email.com", ""]

    with (
        patch("rich.prompt.Prompt.ask", side_effect=inputs),
        patch(
            "zotero_cli.infra.zotero_api.ZoteroAPIClient.resolve_key_identity",
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
    assert "target_group" not in content
    assert 'semantic_scholar_api_key = "ss_key"' in content
    assert 'unpaywall_email = "up@email.com"' in content

    # Issue #236: config.toml holds live API keys - must not be world-readable.
    if os.name != "nt":
        assert stat.S_IMODE(config_file.stat().st_mode) == 0o600


def test_init_command_resolves_identity_and_prefills_user_library_id(tmp_path, capsys):
    config_file = tmp_path / "config.toml"

    # api_key, lib_type, lib_id, ss_key, up_email, database_path
    inputs = ["test_api_key", "user", "999", "ss_key", "", ""]

    with (
        patch("rich.prompt.Prompt.ask", side_effect=inputs) as mock_prompt,
        patch(
            "zotero_cli.infra.zotero_api.ZoteroAPIClient.resolve_key_identity",
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

    # api_key, lib_type, group id, user_id, ss_key, up_email, database_path
    inputs = ["test_api_key", "group", "12345", "", "", "", ""]

    with (
        patch("rich.prompt.Prompt.ask", side_effect=inputs),
        patch(
            "zotero_cli.infra.zotero_api.ZoteroAPIClient.resolve_key_identity",
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
    inputs = ["user_key", "user", "my_uid", "ss_key", "", ""]

    with (
        patch("rich.prompt.Prompt.ask", side_effect=inputs),
        patch(
            "zotero_cli.infra.zotero_api.ZoteroAPIClient.resolve_key_identity",
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
    inputs = ["invalid_key", "user", "123", "", "", ""]

    with (
        patch("rich.prompt.Prompt.ask", side_effect=inputs),
        patch("rich.prompt.Confirm.ask", return_value=True),  # Save anyway? -> Yes
        patch(
            "zotero_cli.infra.zotero_api.ZoteroAPIClient.resolve_key_identity",
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
    inputs = ["new_key", "user", "456", "", "", ""]

    with (
        patch("rich.prompt.Prompt.ask", side_effect=inputs),
        patch("rich.prompt.Confirm.ask", return_value=True),  # Overwrite? -> Yes
        patch(
            "zotero_cli.infra.zotero_api.ZoteroAPIClient.resolve_key_identity",
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


def _run_init(config_file, inputs, confirm=True):
    with (
        patch("rich.prompt.Prompt.ask", side_effect=inputs) as prompt,
        patch("rich.prompt.Confirm.ask", return_value=confirm),
        patch(
            "zotero_cli.infra.zotero_api.ZoteroAPIClient.resolve_key_identity",
            side_effect=Exception("mocked: no network in unit tests"),
        ),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_gw_get,
    ):
        mock_gw_get.return_value.verify_credentials.return_value = True
        with patch.object(sys, "argv", ["zotero-cli", "--config", str(config_file), "init"]):
            main()
    return prompt


def test_init_writes_quotes_and_backslashes_safely(tmp_path):
    """Issue #388: f-string TOML broke on a quote or backslash, and a newline
    could add keys."""
    import tomllib

    config_file = tmp_path / "config.toml"
    key = 'ab"c\\d\nlibrary_type = "group"'
    db = "C:\\Users\\me\\Zotero\\zotero.sqlite"
    _run_init(config_file, [key, "user", "42", "", 'me+"x"@example.org', db])

    data = tomllib.loads(config_file.read_text())["zotero"]
    assert data["api_key"] == key
    assert data["library_type"] == "user"
    assert data["unpaywall_email"] == 'me+"x"@example.org'
    assert data["database_path"] == db


def test_init_keeps_settings_it_doesnt_ask_about(tmp_path):
    """Issue #388: re-running init dropped AI keys, ncbi_api_key, etc."""
    import tomllib

    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[zotero]\napi_key = "old"\nlibrary_id = "1"\nlibrary_type = "user"\n'
        'openai_api_key = "sk-keep"\nncbi_api_key = "ncbi-keep"\ntarget_group = "my-slug"\n'
        '[extraction]\nschema = "keep.yaml"\n'
    )
    # Enter on the key keeps it (the prompt returns its default).
    _run_init(config_file, ["old", "user", "1", "", "", ""])

    data = tomllib.loads(config_file.read_text())
    assert data["zotero"]["api_key"] == "old"
    assert data["zotero"]["openai_api_key"] == "sk-keep"
    assert data["zotero"]["ncbi_api_key"] == "ncbi-keep"
    assert "target_group" not in data["zotero"]
    assert data["extraction"]["schema"] == "keep.yaml"
    if os.name != "nt":
        assert stat.S_IMODE(config_file.stat().st_mode) == 0o600


def test_init_offers_existing_values_as_defaults(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[zotero]\napi_key = "old"\nlibrary_id = "77"\nlibrary_type = "user"\n'
        'database_path = "/data/zotero.sqlite"\n'
    )
    prompt = _run_init(config_file, ["old", "user", "77", "", "", "/data/zotero.sqlite"])

    defaults = {c.args[0]: c.kwargs.get("default") for c in prompt.call_args_list}
    assert defaults["Library Type"] == "user"
    assert defaults["Library ID (your User ID)"] == "77"
    assert defaults["Path to zotero.sqlite, for --offline (optional)"] == "/data/zotero.sqlite"


def test_init_defaults_to_the_user_library(tmp_path):
    """Issue #397/#388: most first-time users have a personal library."""
    prompt = _run_init(tmp_path / "config.toml", ["k", "user", "5", "", "", ""])
    type_call = next(c for c in prompt.call_args_list if c.args[0] == "Library Type")
    assert type_call.kwargs["default"] == "user"


def test_init_takes_the_group_id_from_a_url(tmp_path, capsys):
    """The old prompt asked for a slug the loader couldn't use."""
    import tomllib

    config_file = tmp_path / "config.toml"
    _run_init(
        config_file,
        ["k", "group", "my-research-group", "https://www.zotero.org/groups/6287212/rsl-xm", "", "", "", ""],
    )

    data = tomllib.loads(config_file.read_text())["zotero"]
    assert data["library_id"] == "6287212"
    assert data["library_type"] == "group"
    assert "group's number" in capsys.readouterr().out
