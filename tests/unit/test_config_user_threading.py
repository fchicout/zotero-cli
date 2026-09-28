"""--config and --user reach every command (Issue #383)."""

import argparse
from unittest.mock import MagicMock, patch

import toml

from zotero_cli.core.config import ConfigManager, get_config, reset_config


def test_config_manager_writes_the_loaded_config_not_the_default(tmp_path, monkeypatch):
    """`system switch` / `rag model set` under --config edited the default file."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    profile = tmp_path / "lab.toml"
    profile.write_text('[zotero]\napi_key = "k"\nlibrary_id = "1"\nlibrary_type = "group"\n')
    try:
        get_config(str(profile))
        ConfigManager().save_group_context("999")
    finally:
        reset_config()

    assert toml.load(profile)["zotero"]["library_id"] == "999"
    assert toml.load(profile)["zotero"]["api_key"] == "k"
    assert not (tmp_path / "xdg" / "zotero-cli" / "config.toml").exists()


def test_storage_checkout_honours_user():
    from zotero_cli.cli.commands.storage_cmd import StorageCommand

    args = argparse.Namespace(subcommand="checkout", limit=1, user=True, allow_group_library=False)
    with (
        patch("zotero_cli.cli.commands.storage_cmd.get_config", return_value=MagicMock()),
        patch(
            "zotero_cli.cli.commands.storage_cmd.GatewayFactory.get_zotero_gateway"
        ) as get_gateway,
        patch("zotero_cli.cli.commands.storage_cmd.StorageService") as service,
    ):
        service.return_value.checkout_items.return_value = 0
        StorageCommand()._handle_checkout(args)

    assert get_gateway.call_args.kwargs["force_user"] is True


def test_slr_report_status_honours_user():
    from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand

    args = argparse.Namespace(report_verb="status", collection="C", all_sources=False, user=True)
    with patch(
        "zotero_cli.cli.commands.slr.report_cmd.GatewayFactory.get_slr_status_service"
    ) as get_service:
        get_service.return_value.get_slr_status.return_value = [MagicMock()]
        SLRReportCommand._handle_status(MagicMock(), args)

    assert get_service.call_args.kwargs["force_user"] is True
