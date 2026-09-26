"""Issue #378: `storage checkout` gains --dry-run/--execute. Moving stays the
3.x default (docs/COMPATIBILITY.md), with a warning when neither is given."""

import argparse
from unittest.mock import patch

import pytest

from zotero_cli.cli.commands.storage_cmd import StorageCommand


def _args(**kwargs) -> argparse.Namespace:
    base = dict(subcommand="checkout", limit=5, allow_group_library=False, dry_run=False, execute=False)
    base.update(kwargs)
    return argparse.Namespace(**base)


@pytest.mark.parametrize(
    "flags, dry_run, warns",
    [({}, False, True), ({"execute": True}, False, False), ({"dry_run": True}, True, False)],
)
def test_checkout_modes(capsys, flags, dry_run, warns):
    with (
        patch("zotero_cli.cli.commands.storage_cmd.get_config"),
        patch("zotero_cli.cli.commands.storage_cmd.GatewayFactory"),
        patch("zotero_cli.cli.commands.storage_cmd.StorageService") as service,
    ):
        service.return_value.checkout_items.return_value = 2
        StorageCommand().execute(_args(**flags))

    service.return_value.checkout_items.assert_called_once_with(
        limit=5, allow_group_library=False, dry_run=dry_run
    )
    captured = capsys.readouterr()
    assert ("from 4.0" in captured.err) is warns
    assert ("nothing was changed" in captured.out) is dry_run


def test_dry_run_and_execute_are_exclusive():
    parser = argparse.ArgumentParser()
    StorageCommand().register_args(parser)
    with pytest.raises(SystemExit):
        parser.parse_args(["checkout", "--dry-run", "--execute"])
