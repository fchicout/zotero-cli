import argparse
import json
from unittest.mock import Mock, patch

import pytest

from zotero_cli.cli.commands.item_cmd import ItemCommand
from zotero_cli.core.services.enrichment_service import DEFAULT_FIELDS, HydrationResult


@pytest.fixture
def item_cmd():
    return ItemCommand()


def _args(**kw):
    base = dict(
        verb="hydrate",
        key=None,
        collection=None,
        all=False,
        fields=None,
        overwrite=False,
        by_title=False,
        execute=False,
        dry_run=False,
        format="table",
        user=False,
        offline=False,
    )
    base.update(kw)
    return argparse.Namespace(**base)


def _result(status="proposed"):
    return HydrationResult(
        key="K1",
        title="T1",
        status=status,
        identifier="doi:10.1/x",
        source="metadata providers",
        changes={"abstractNote": {"old": "", "new": "Abs"}},
    )


@patch("zotero_cli.infra.factory.GatewayFactory.get_enrichment_service")
def test_previews_by_default(mock_factory, item_cmd, capsys):
    service = Mock()
    service.hydrate_item.return_value = _result()
    mock_factory.return_value = service

    item_cmd.execute(_args(key="K1"))

    service.hydrate_item.assert_called_once_with(
        "K1", fields=DEFAULT_FIELDS, overwrite=False, by_title=False, execute=False
    )
    out = capsys.readouterr().out
    assert "PREVIEW" in out and "--execute" in out


@patch("zotero_cli.infra.factory.GatewayFactory.get_enrichment_service")
def test_execute_and_options_are_passed_through(mock_factory, item_cmd):
    service = Mock()
    service.hydrate_collection.return_value = [_result("updated")]
    mock_factory.return_value = service

    item_cmd.execute(
        _args(collection="MyCol", execute=True, overwrite=True, by_title=True, fields="abstract")
    )

    service.hydrate_collection.assert_called_once_with(
        "MyCol", fields=("abstract",), overwrite=True, by_title=True, execute=True
    )


@patch("zotero_cli.infra.factory.GatewayFactory.get_enrichment_service")
def test_json_output_is_only_json_on_stdout(mock_factory, item_cmd, capsys):
    service = Mock()
    service.hydrate_all.return_value = [_result(), _result("no-identifier")]
    mock_factory.return_value = service

    item_cmd.execute(_args(all=True, format="json"))

    data = json.loads(capsys.readouterr().out)
    assert [r["status"] for r in data] == ["proposed", "no-identifier"]
    assert data[0]["changes"] == {"abstractNote": {"old": "", "new": "Abs"}}


@patch("zotero_cli.infra.factory.GatewayFactory.get_enrichment_service")
def test_unknown_field_is_a_usage_error(mock_factory, item_cmd, capsys):
    with pytest.raises(SystemExit) as exc:
        item_cmd.execute(_args(key="K1", fields="volume"))
    assert exc.value.code == 2
    assert "volume" in capsys.readouterr().err
    mock_factory.assert_not_called()


@patch("zotero_cli.infra.factory.GatewayFactory.get_enrichment_service")
def test_execute_is_refused_offline(mock_factory, item_cmd, capsys):
    with pytest.raises(SystemExit) as exc:
        item_cmd.execute(_args(key="K1", execute=True, offline=True))
    assert exc.value.code == 2
    assert "read-only" in capsys.readouterr().err
    mock_factory.assert_not_called()


def test_parser_rejects_execute_with_dry_run():
    parser = argparse.ArgumentParser()
    ItemCommand().register_args(parser)
    with pytest.raises(SystemExit):
        parser.parse_args(["hydrate", "--key", "K1", "--execute", "--dry-run"])
