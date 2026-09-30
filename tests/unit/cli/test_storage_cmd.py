import argparse
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.cli.commands.storage_cmd import StorageCommand


@pytest.fixture
def mock_service():
    with (
        patch("zotero_cli.cli.commands.storage_cmd.get_config") as mock_get_config,
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"),
        patch("zotero_cli.cli.commands.storage_cmd.StorageService") as mock_service_cls,
    ):
        mock_get_config.return_value = MagicMock()
        service = mock_service_cls.return_value
        yield service


def _checkout_args(**overrides):
    args = argparse.Namespace(
        subcommand="checkout",
        limit=50,
        allow_group_library=False,
        dry_run=False,
        execute=False,
        user=False,
    )
    for name, value in overrides.items():
        setattr(args, name, value)
    return args


def test_checkout_warns_when_neither_flag_given(mock_service, capsys):
    """Issue #378: `storage checkout` predates preview-by-default and still
    checks out immediately without --dry-run/--execute, but must now warn."""
    mock_service.checkout_items.return_value = 3

    StorageCommand().execute(_checkout_args())

    mock_service.checkout_items.assert_called_once_with(
        limit=50, allow_group_library=False, dry_run=False
    )
    err = capsys.readouterr().err
    assert "currently applies its changes by default" in err
    assert "--execute" in err


def test_checkout_execute_no_warning(mock_service, capsys):
    mock_service.checkout_items.return_value = 3

    StorageCommand().execute(_checkout_args(execute=True))

    mock_service.checkout_items.assert_called_once_with(
        limit=50, allow_group_library=False, dry_run=False
    )
    assert "currently applies its changes by default" not in capsys.readouterr().err


def test_checkout_dry_run_no_warning_and_previews(mock_service, capsys):
    mock_service.checkout_items.return_value = 3

    StorageCommand().execute(_checkout_args(dry_run=True))

    mock_service.checkout_items.assert_called_once_with(
        limit=50, allow_group_library=False, dry_run=True
    )
    out = capsys.readouterr().out
    assert "Would process 3 items" in out
    assert "currently applies its changes by default" not in capsys.readouterr().err


def test_checkout_dry_run_and_execute_are_mutually_exclusive():
    """Issue #378: passing both flags together is refused, not silently
    resolved one way or the other."""
    parser = argparse.ArgumentParser()
    StorageCommand().register_args(parser)

    with pytest.raises(SystemExit):
        parser.parse_args(["checkout", "--dry-run", "--execute"])
