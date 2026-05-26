import argparse
from unittest.mock import MagicMock, mock_open, patch

import pytest

from zotero_cli.cli.commands.slr.source_cmd import SLRSourceCommand
from zotero_cli.core.zotero_item import ZoteroItem


def test_register_args():
    parser = argparse.ArgumentParser()
    SLRSourceCommand.register_args(parser)
    # Just verify that registering args doesn't raise any errors and we can parse a valid command
    args = parser.parse_args(["init", "--name", "testsrc"])
    assert args.source_verb == "init"
    assert args.name == "testsrc"


def test_handle_init_collection_does_not_exist():
    mock_gateway = MagicMock()
    mock_gateway.get_collection_id_by_name.return_value = None
    mock_gateway.create_collection.side_effect = ["PARENT_KEY", "K1", "K2", "K3", "K4"]

    args = argparse.Namespace(
        source_verb="init",
        name="acm"
    )

    SLRSourceCommand.execute(mock_gateway, args)

    mock_gateway.get_collection_id_by_name.assert_called_once_with("raw_acm")
    assert mock_gateway.create_collection.call_count == 5
    # The first creation call is for the parent
    mock_gateway.create_collection.assert_any_call("raw_acm")
    # Subsequent calls are for phases with parent_key
    mock_gateway.create_collection.assert_any_call("01_title_abstract", parent_key="PARENT_KEY")


def test_handle_init_collection_already_exists():
    mock_gateway = MagicMock()
    mock_gateway.get_collection_id_by_name.return_value = "EXISTING_KEY"
    mock_gateway.create_collection.return_value = "SUB_KEY"

    args = argparse.Namespace(
        source_verb="init",
        name="ieee"
    )

    SLRSourceCommand.execute(mock_gateway, args)

    mock_gateway.get_collection_id_by_name.assert_called_once_with("raw_ieee")
    # parent shouldn't be created, but the 4 sub-collections should be
    assert mock_gateway.create_collection.call_count == 4
    mock_gateway.create_collection.assert_any_call("01_title_abstract", parent_key="EXISTING_KEY")


def test_handle_add_collection_not_found():
    mock_gateway = MagicMock()
    mock_gateway.get_collection_id_by_name.return_value = None

    args = argparse.Namespace(
        source_verb="add",
        name="nonexistent",
        file="test.ris",
        verbose=False
    )

    with pytest.raises(SystemExit) as excinfo:
        SLRSourceCommand.execute(mock_gateway, args)
    assert excinfo.value.code == 1


@patch("zotero_cli.infra.factory.GatewayFactory.get_import_service")
@patch("zotero_cli.infra.factory.GatewayFactory.get_ris_gateway")
@patch("zotero_cli.core.strategies.RisImportStrategy.fetch_papers")
def test_handle_add_ris_success(mock_fetch, mock_ris_gateway, mock_import_service):
    mock_gateway = MagicMock()
    mock_gateway.get_collection_id_by_name.return_value = "RAW_KEY"

    mock_papers = [MagicMock()]
    mock_fetch.return_value = mock_papers

    mock_imp_service = MagicMock()
    mock_imp_service.import_papers.return_value = 5
    mock_import_service.return_value = mock_imp_service

    args = argparse.Namespace(
        source_verb="add",
        name="acm",
        file="test.ris",
        verbose=True
    )

    SLRSourceCommand.execute(mock_gateway, args)

    mock_fetch.assert_called_once_with("test.ris")
    mock_imp_service.import_papers.assert_called_once_with(mock_papers, "RAW_KEY", verbose=True)


@patch("zotero_cli.infra.factory.GatewayFactory.get_import_service")
@patch("zotero_cli.infra.factory.GatewayFactory.get_bibtex_gateway")
@patch("zotero_cli.core.strategies.BibtexImportStrategy.fetch_papers")
def test_handle_add_bib_success(mock_fetch, mock_bib_gateway, mock_import_service):
    mock_gateway = MagicMock()
    mock_gateway.get_collection_id_by_name.return_value = "RAW_KEY"

    mock_papers = [MagicMock()]
    mock_fetch.return_value = mock_papers

    mock_imp_service = MagicMock()
    mock_imp_service.import_papers.return_value = 3
    mock_import_service.return_value = mock_imp_service

    args = argparse.Namespace(
        source_verb="add",
        name="acm",
        file="test.bib",
        verbose=False
    )

    SLRSourceCommand.execute(mock_gateway, args)

    mock_fetch.assert_called_once_with("test.bib")
    mock_imp_service.import_papers.assert_called_once_with(mock_papers, "RAW_KEY", verbose=False)


@patch("builtins.open", new_callable=mock_open, read_data="item title,abstract\n")
@patch("zotero_cli.infra.factory.GatewayFactory.get_import_service")
@patch("zotero_cli.infra.factory.GatewayFactory.get_springer_csv_gateway")
@patch("zotero_cli.core.strategies.SpringerCsvImportStrategy.fetch_papers")
def test_handle_add_springer_csv_success(mock_fetch, mock_springer_gateway, mock_import_service, mock_file):
    mock_gateway = MagicMock()
    mock_gateway.get_collection_id_by_name.return_value = "RAW_KEY"

    mock_papers = [MagicMock()]
    mock_fetch.return_value = mock_papers

    mock_imp_service = MagicMock()
    mock_imp_service.import_papers.return_value = 10
    mock_import_service.return_value = mock_imp_service

    args = argparse.Namespace(
        source_verb="add",
        name="acm",
        file="test.csv",
        verbose=False
    )

    SLRSourceCommand.execute(mock_gateway, args)

    mock_fetch.assert_called_once_with("test.csv")
    mock_imp_service.import_papers.assert_called_once_with(mock_papers, "RAW_KEY", verbose=False)


@patch("builtins.open", new_callable=mock_open, read_data="document title,abstract\n")
@patch("zotero_cli.infra.factory.GatewayFactory.get_import_service")
@patch("zotero_cli.infra.factory.GatewayFactory.get_ieee_csv_gateway")
@patch("zotero_cli.core.strategies.IeeeCsvImportStrategy.fetch_papers")
def test_handle_add_ieee_csv_success(mock_fetch, mock_ieee_gateway, mock_import_service, mock_file):
    mock_gateway = MagicMock()
    mock_gateway.get_collection_id_by_name.return_value = "RAW_KEY"

    mock_papers = [MagicMock()]
    mock_fetch.return_value = mock_papers

    mock_imp_service = MagicMock()
    mock_imp_service.import_papers.return_value = 8
    mock_import_service.return_value = mock_imp_service

    args = argparse.Namespace(
        source_verb="add",
        name="acm",
        file="test.csv",
        verbose=False
    )

    SLRSourceCommand.execute(mock_gateway, args)

    mock_fetch.assert_called_once_with("test.csv")
    mock_imp_service.import_papers.assert_called_once_with(mock_papers, "RAW_KEY", verbose=False)


@patch("builtins.open", new_callable=mock_open, read_data="title,doi\n")
@patch("zotero_cli.infra.factory.GatewayFactory.get_import_service")
@patch("zotero_cli.infra.factory.GatewayFactory.get_canonical_csv_gateway")
@patch("zotero_cli.core.strategies.CanonicalCsvImportStrategy.fetch_papers")
def test_handle_add_canonical_csv_success(mock_fetch, mock_canonical_gateway, mock_import_service, mock_file):
    mock_gateway = MagicMock()
    mock_gateway.get_collection_id_by_name.return_value = "RAW_KEY"

    mock_papers = [MagicMock()]
    mock_fetch.return_value = mock_papers

    mock_imp_service = MagicMock()
    mock_imp_service.import_papers.return_value = 2
    mock_import_service.return_value = mock_imp_service

    args = argparse.Namespace(
        source_verb="add",
        name="acm",
        file="test.csv",
        verbose=False
    )

    SLRSourceCommand.execute(mock_gateway, args)

    mock_fetch.assert_called_once_with("test.csv")
    mock_imp_service.import_papers.assert_called_once_with(mock_papers, "RAW_KEY", verbose=False)


@patch("builtins.open", new_callable=mock_open, read_data="unknown,headers\n")
def test_handle_add_unknown_csv(mock_file):
    mock_gateway = MagicMock()
    mock_gateway.get_collection_id_by_name.return_value = "RAW_KEY"

    args = argparse.Namespace(
        source_verb="add",
        name="acm",
        file="test.csv",
        verbose=False
    )

    with pytest.raises(SystemExit) as excinfo:
        SLRSourceCommand.execute(mock_gateway, args)
    assert excinfo.value.code == 1


def test_handle_add_unsupported_ext():
    mock_gateway = MagicMock()
    mock_gateway.get_collection_id_by_name.return_value = "RAW_KEY"

    args = argparse.Namespace(
        source_verb="add",
        name="acm",
        file="test.txt",
        verbose=False
    )

    with pytest.raises(SystemExit) as excinfo:
        SLRSourceCommand.execute(mock_gateway, args)
    assert excinfo.value.code == 1


def test_handle_list_no_collections(capsys):
    mock_gateway = MagicMock()
    mock_gateway.get_all_collections.return_value = []

    args = argparse.Namespace(source_verb="list")

    SLRSourceCommand.execute(mock_gateway, args)

    out = capsys.readouterr().out
    assert "No active SLR sources found" in out


def test_handle_list_success(capsys):
    mock_gateway = MagicMock()
    mock_gateway.get_all_collections.return_value = [
        {"key": "RAW_KEY", "data": {"name": "raw_acm"}}
    ]

    # 2 items in raw collection
    mock_item1 = ZoteroItem(key="K1", version=1, item_type="journalArticle", title="Paper 1")
    mock_item1.raw_data = {
        "data": {
            "title": "Paper 1",
            "abstractNote": "My Abstract",
            "DOI": "10.1000/xyz123",
            "extra": "arxiv: 2101.00000"
        }
    }

    # K2 has missing abstract, no doi, no pdf, no note
    mock_item2 = ZoteroItem(key="K2", version=1, item_type="journalArticle", title="Paper 2")
    mock_item2.raw_data = {
        "data": {
            "title": "Paper 2"
        }
    }

    mock_gateway.get_items_in_collection.return_value = [mock_item1, mock_item2]

    # Item children (PDF or Notes)
    # mock_item1 has a PDF child and SDB note child
    mock_gateway.get_item_children.side_effect = lambda key: (
        [
            {"data": {"itemType": "attachment", "contentType": "application/pdf"}},
            {"data": {"itemType": "note", "note": "<div>Decision: include</div>"}}
        ] if key == "K1" else []
    )

    args = argparse.Namespace(source_verb="list")

    SLRSourceCommand.execute(mock_gateway, args)

    out = capsys.readouterr().out
    assert "Active SLR Sources & Pipeline Health" in out
    assert "raw_acm" in out
    assert "2" in out  # Total Items
    assert "1/2" in out  # PDF count


def test_handle_list_success_empty_source(capsys):
    mock_gateway = MagicMock()
    mock_gateway.get_all_collections.return_value = [
        {"key": "RAW_KEY", "data": {"name": "raw_acm"}}
    ]
    mock_gateway.get_items_in_collection.return_value = []

    args = argparse.Namespace(source_verb="list")
    SLRSourceCommand.execute(mock_gateway, args)

    out = capsys.readouterr().out
    assert "Active SLR Sources & Pipeline Health" in out
    assert "raw_acm" in out
    assert "0" in out

