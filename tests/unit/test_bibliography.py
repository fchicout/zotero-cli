"""Issue #534: `--as bibliography`, formatted through bxc."""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.cli.commands.collection_cmd import CollectionCommand
from zotero_cli.cli.commands.item_cmd import ItemCommand
from zotero_cli.cli.main import build_parser
from zotero_cli.core.exceptions import UsageError
from zotero_cli.core.services.export_service import ExportService
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.bxc_formatter import BxcBibliographyFormatter

BIB = '@article{k,author={M{\\"u}ller, Hans},title={A title},journal={J},year={2020}}'


def test_formatter_renders_the_bundled_style_with_unicode_authors():
    text = BxcBibliographyFormatter(offline=True).format(BIB, "apa")
    assert "Müller, H. (2020). A title." in text


def test_formatter_renderings_differ():
    formatter = BxcBibliographyFormatter(offline=True)
    assert "<" in formatter.format(BIB, "apa", "html")
    assert "<" not in formatter.format(BIB, "apa", "plain")


def test_unknown_style_is_a_usage_error_with_matches():
    formatter = BxcBibliographyFormatter(offline=True)
    with pytest.raises(UsageError, match="Unknown citation style 'apaa'.*apa"):
        formatter.format(BIB, "apaa")


def test_unknown_rendering_is_a_usage_error():
    formatter = BxcBibliographyFormatter(offline=True)
    with pytest.raises(UsageError, match="Unknown rendering"):
        formatter.format(BIB, "apa", "pdf")


def test_formatter_never_writes_the_cache_and_honours_offline():
    with patch("bxc.format_bibtex", return_value="x") as fmt:
        BxcBibliographyFormatter(offline=True).format(BIB, "apa")
    assert fmt.call_args.kwargs == {"output_format": "plain", "cache": False, "offline": True}


def _service(formatter=None):
    sdb = MagicMock()
    sdb.inspect_items_sdb.return_value = {}
    bibtex = MagicMock()
    bibtex.serialize.return_value = BIB
    return ExportService(MagicMock(), bibtex, MagicMock(), sdb, formatter)


def _item():
    return ZoteroItem(key="K", version=1, item_type="journalArticle", title="A title")


def test_service_formats_the_serialized_bibtex():
    formatter = MagicMock()
    formatter.format.return_value = "REF"
    assert _service(formatter).serialize_bibliography([_item()], "ieee", "html") == "REF"
    formatter.format.assert_called_once_with(BIB, "ieee", "html")


def test_service_without_items_to_format_returns_nothing():
    formatter = MagicMock()
    service = _service(formatter)
    service.bibtex_gateway.serialize.return_value = ""
    assert service.serialize_bibliography([_item()]) == ""
    formatter.format.assert_not_called()


def test_service_writes_the_bibliography_file(tmp_path):
    formatter = MagicMock()
    formatter.format.return_value = "REF"
    out = tmp_path / "refs.txt"
    assert _service(formatter).export_bibliography([_item()], str(out)) is True
    assert out.read_text(encoding="utf-8") == "REF\n"


def test_flags_default_to_apa_plain_and_accept_bibliography():
    args = build_parser().parse_args(["item", "export", "--key", "K", "--as", "bibliography"])
    assert (args.export_format, args.style, args.render) == ("bibliography", "apa", "plain")
    args = build_parser().parse_args(
        ["collection", "export", "--collection", "C", "--as", "bibliography",
         "--style", "ieee", "--render", "markdown"]
    )
    assert (args.style, args.render) == ("ieee", "markdown")
    args = build_parser().parse_args(["item", "inspect", "K", "--as", "bibliography"])
    assert args.export_format == "bibliography"


def test_item_export_without_output_prints(capsys):
    service = MagicMock()
    service.serialize_bibliography.return_value = "REF"
    gateway = MagicMock()
    gateway.get_item.return_value = _item()
    args = argparse.Namespace(
        verb="export", key="K", export_format="bibliography", output=None, user=False,
        style="ieee", render="html",
    )
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=gateway),
        patch("zotero_cli.infra.factory.GatewayFactory.get_export_service", return_value=service),
    ):
        ItemCommand().execute(args)
    service.serialize_bibliography.assert_called_once_with([gateway.get_item.return_value], "ieee", "html")
    assert capsys.readouterr().out.strip() == "REF"


def test_collection_export_without_output_prints(capsys):
    service = MagicMock()
    service.collection_bibliography.return_value = "REF"
    args = argparse.Namespace(
        verb="export", collection="C", export_format="bibliography", output=None, user=False,
        style="apa", render="plain",
    )
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_export_service", return_value=service),
    ):
        CollectionCommand().execute(args)
    service.collection_bibliography.assert_called_once_with("C", "apa", "plain")
    assert capsys.readouterr().out.strip() == "REF"


def test_collection_export_to_file_passes_style_and_render():
    service = MagicMock()
    service.export_collection.return_value = True
    args = argparse.Namespace(
        verb="export", collection="C", export_format="bibliography", output="o.txt", user=False,
        style="ieee", render="html",
    )
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_export_service", return_value=service),
    ):
        CollectionCommand().execute(args)
    service.export_collection.assert_called_once_with("C", "o.txt", "bibliography", "ieee", "html")


def test_unknown_style_without_any_close_match_keeps_bxc_message():
    formatter = BxcBibliographyFormatter(offline=True)
    with pytest.raises(UsageError, match="not in the bundled styles"):
        formatter.format(BIB, "zzzzzzzzzzzzqqq")


def test_service_without_a_formatter_says_so():
    service = _service(None)
    item = _item()
    with pytest.raises(RuntimeError, match="No bibliography formatter"):
        service.serialize_bibliography([item])


def test_service_does_not_write_an_empty_bibliography(tmp_path, capsys):
    formatter = MagicMock()
    service = _service(formatter)
    service.bibtex_gateway.serialize.return_value = ""
    out = tmp_path / "refs.txt"
    assert service.export_bibliography([_item()], str(out)) is False
    assert not out.exists()
    assert "No valid papers" in capsys.readouterr().err


def test_collection_bibliography_and_export_use_the_collection_items():
    formatter = MagicMock()
    formatter.format.return_value = "REF"
    service = _service(formatter)
    service.collection_repo.get_collection_id_by_name.return_value = "C1"
    service.collection_repo.get_items_in_collection.return_value = [_item()]
    assert service.collection_bibliography("C", "ieee", "html") == "REF"
    formatter.format.assert_called_once_with(BIB, "ieee", "html")


def test_collection_bibliography_missing_collection_is_none(capsys):
    service = _service(MagicMock())
    service.collection_repo.get_collection_id_by_name.return_value = None
    assert service.collection_bibliography("Nope") is None
    assert "not found" in capsys.readouterr().err


def test_collection_export_to_file_via_the_service(tmp_path):
    formatter = MagicMock()
    formatter.format.return_value = "REF"
    service = _service(formatter)
    service.collection_repo.get_collection_id_by_name.return_value = "C1"
    service.collection_repo.get_items_in_collection.return_value = [_item()]
    out = tmp_path / "c.txt"
    assert service.export_collection("C", str(out), "bibliography", "apa", "plain") is True
    assert out.read_text(encoding="utf-8") == "REF\n"


def test_collection_export_without_output_exits_when_nothing_to_print():
    service = MagicMock()
    service.collection_bibliography.return_value = None
    args = argparse.Namespace(
        verb="export", collection="C", export_format="bibliography", output=None, user=False,
        style="apa", render="plain",
    )
    command = CollectionCommand()
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_export_service", return_value=service),
        pytest.raises(SystemExit),
    ):
        command.execute(args)


def test_item_export_to_file_writes_the_bibliography(capsys):
    service = MagicMock()
    service.export_bibliography.return_value = True
    gateway = MagicMock()
    gateway.get_item.return_value = _item()
    args = argparse.Namespace(
        verb="export", key="K", export_format="bibliography", output="o.txt", user=False,
        style="apa", render="plain",
    )
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=gateway),
        patch("zotero_cli.infra.factory.GatewayFactory.get_export_service", return_value=service),
    ):
        ItemCommand().execute(args)
    service.export_bibliography.assert_called_once_with(
        [gateway.get_item.return_value], "o.txt", "apa", "plain"
    )
    assert "Export complete" in capsys.readouterr().out


def test_item_inspect_prints_the_bibliography(capsys):
    service = MagicMock()
    service.serialize_bibliography.return_value = "REF\x1b[31m"
    gateway = MagicMock()
    gateway.get_item.return_value = _item()
    args = argparse.Namespace(
        key="K", file=None, raw=False, export_format="bibliography", style="apa", render="plain",
        full_notes=False, user=False, details=False, verb="inspect",
    )
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=gateway),
        patch("zotero_cli.infra.factory.GatewayFactory.get_export_service", return_value=service),
    ):
        ItemCommand().execute(args)
    out = capsys.readouterr().out
    assert "REF" in out
    assert "\x1b" not in out
