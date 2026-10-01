import argparse
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.cli.commands.slr.extraction_cmd import ExtractionCommand
from zotero_cli.core.exceptions import ZoteroCliError


@pytest.fixture
def mock_deps():
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mg,
        patch("zotero_cli.infra.factory.GatewayFactory.get_extraction_service") as me,
    ):
        yield mg.return_value, me.return_value


def test_extraction_command_key(mock_deps, capsys):
    mock_gateway, mock_service = mock_deps
    from zotero_cli.core.zotero_item import ZoteroItem

    mock_item = ZoteroItem(key="K1", version=1, item_type="journalArticle", title="Paper 1")
    mock_gateway.get_item.return_value = mock_item

    with patch("zotero_cli.cli.tui.factory.TUIFactory.get_extraction_tui") as mock_tui_factory:
        mock_tui = mock_tui_factory.return_value
        args = argparse.Namespace(
            verb="extraction",
            key="K1",
            collection=None,
            agent=False,
            persona=None,
            export=None,
            user=False,
        )
        ExtractionCommand.execute(args)

        mock_tui.run_extraction.assert_called_once_with([mock_item], agent=False, persona=None)


def test_extraction_command_collection(mock_deps, capsys):
    mock_gateway, mock_service = mock_deps
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    mock_item = MagicMock()
    mock_gateway.get_items_in_collection.return_value = [mock_item]

    with patch("zotero_cli.cli.tui.factory.TUIFactory.get_extraction_tui") as mock_tui_factory:
        mock_tui = mock_tui_factory.return_value
        args = argparse.Namespace(
            verb="extraction",
            key=None,
            collection="MyCol",
            agent=True,
            persona="Paula",
            export=None,
            user=False,
        )
        ExtractionCommand.execute(args)

        mock_tui.run_extraction.assert_called_once_with([mock_item], agent=True, persona="Paula")


def test_extraction_command_no_items(mock_deps, capsys):
    mock_gateway, mock_service = mock_deps
    mock_gateway.get_item.return_value = None

    args = argparse.Namespace(
        verb="extraction",
        key="MISSING",
        collection=None,
        agent=False,
        persona=None,
        export=None,
        user=False,
    )
    with pytest.raises(ZoteroCliError) as raised:
        ExtractionCommand.execute(args)

    out = str(raised.value)
    assert "No items found for extraction" in out


def _export_args(path, persona="Paula"):
    return argparse.Namespace(
        verb="extraction",
        key=None,
        collection="MyCol",
        agent=False,
        persona=persona,
        export=path,
        user=False,
    )


@pytest.mark.parametrize(
    ("path", "fmt"),
    [("m.json", "json"), ("m.md", "markdown"), ("m.csv", "csv"), ("m.xlsx", "csv")],
)
def test_export_writes_the_matrix_in_the_format_of_the_extension(mock_deps, capsys, path, fmt):
    mock_gateway, mock_service = mock_deps
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    item = MagicMock()
    mock_gateway.get_items_in_collection.return_value = [item]
    mock_service.export_matrix.return_value = path

    ExtractionCommand.execute(_export_args(path))

    mock_service.export_matrix.assert_called_once_with(
        [item], output_format=fmt, persona="Paula", output_path=path
    )
    assert f"Exported extraction matrix to: {path}" in capsys.readouterr().out


def test_export_does_not_open_the_extraction_tui(mock_deps):
    mock_gateway, mock_service = mock_deps
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    mock_gateway.get_items_in_collection.return_value = [MagicMock()]
    mock_service.export_matrix.return_value = "m.csv"

    with patch("zotero_cli.cli.tui.factory.TUIFactory.get_extraction_tui") as tui_factory:
        ExtractionCommand.execute(_export_args("m.csv"))

    tui_factory.assert_not_called()


def test_export_without_persona_uses_the_services_default(mock_deps):
    mock_gateway, mock_service = mock_deps
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    mock_gateway.get_items_in_collection.return_value = [MagicMock()]
    mock_service.export_matrix.return_value = "m.csv"

    ExtractionCommand.execute(_export_args("m.csv", persona=None))

    assert mock_service.export_matrix.call_args.kwargs["persona"] == "unknown"


def test_export_without_a_schema_is_a_clear_error(mock_deps):
    mock_gateway, mock_service = mock_deps
    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    mock_gateway.get_items_in_collection.return_value = [MagicMock()]
    mock_service.export_matrix.side_effect = FileNotFoundError("Schema file not found: schema.yaml")
    args = _export_args("m.csv")

    with pytest.raises(ZoteroCliError, match="Cannot export the extraction matrix.*schema.yaml"):
        ExtractionCommand.execute(args)
