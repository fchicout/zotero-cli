import argparse
from unittest.mock import MagicMock, mock_open, patch

import pytest

from zotero_cli.cli.commands.import_cmd import ImportCommand


@pytest.fixture
def mock_import_service():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_import_service") as mock_get:
        service = MagicMock()
        mock_get.return_value = service
        yield service


def test_import_register_args():
    parser = argparse.ArgumentParser()
    ImportCommand().register_args(parser)
    actions = parser._actions
    assert len(actions) > 0


@patch("os.path.splitext", return_value=("file", ".bib"))
def test_import_file_bib(mock_splitext, mock_import_service, capsys):
    args = argparse.Namespace(
        verb="import",
        import_type="file",
        file="references.bib",
        collection="COL123",
        verbose=True,
        user=False
    )
    mock_import_service.import_papers.return_value = 2

    with patch("zotero_cli.infra.factory.GatewayFactory.get_bibtex_gateway"):
        strategy_mock = MagicMock()
        strategy_mock.fetch_papers.return_value = []
        with patch("zotero_cli.core.strategies.BibtexImportStrategy", return_value=strategy_mock):
            ImportCommand().execute(args)

    out = capsys.readouterr().out
    assert "Imported 2 items." in out


@patch("os.path.splitext", return_value=("file", ".ris"))
def test_import_file_ris(mock_splitext, mock_import_service, capsys):
    args = argparse.Namespace(
        verb="import",
        import_type="file",
        file="references.ris",
        collection="COL123",
        verbose=True,
        user=False
    )
    mock_import_service.import_papers.return_value = 1

    with patch("zotero_cli.infra.factory.GatewayFactory.get_ris_gateway"):
        strategy_mock = MagicMock()
        strategy_mock.fetch_papers.return_value = []
        with patch("zotero_cli.core.strategies.RisImportStrategy", return_value=strategy_mock):
            ImportCommand().execute(args)

    out = capsys.readouterr().out
    assert "Imported 1 items." in out


@patch("os.path.splitext", return_value=("file", ".csv"))
@patch("builtins.open", new_callable=mock_open, read_data="item title,authors\n")
def test_import_file_springer_csv(mock_file, mock_splitext, mock_import_service, capsys):
    args = argparse.Namespace(
        verb="import",
        import_type="file",
        file="springer.csv",
        collection="COL123",
        verbose=True,
        user=False
    )
    mock_import_service.import_papers.return_value = 5

    with patch("zotero_cli.infra.factory.GatewayFactory.get_springer_csv_gateway"):
        strategy_mock = MagicMock()
        strategy_mock.fetch_papers.return_value = []
        with patch("zotero_cli.core.strategies.SpringerCsvImportStrategy", return_value=strategy_mock):
            ImportCommand().execute(args)

    out = capsys.readouterr().out
    assert "Imported 5 items." in out


@patch("os.path.splitext", return_value=("file", ".csv"))
@patch("builtins.open", new_callable=mock_open, read_data="title,doi\n")
def test_import_file_canonical_csv(mock_file, mock_splitext, mock_import_service, capsys):
    args = argparse.Namespace(
        verb="import",
        import_type="file",
        file="canonical.csv",
        collection="COL123",
        verbose=True,
        user=False
    )
    mock_import_service.import_papers.return_value = 3

    with patch("zotero_cli.infra.factory.GatewayFactory.get_canonical_csv_gateway"):
        strategy_mock = MagicMock()
        strategy_mock.fetch_papers.return_value = []
        with patch("zotero_cli.core.strategies.CanonicalCsvImportStrategy", return_value=strategy_mock):
            ImportCommand().execute(args)

    out = capsys.readouterr().out
    assert "Imported 3 items." in out


@patch("os.path.splitext", return_value=("file", ".csv"))
@patch("builtins.open", new_callable=mock_open, read_data="unknown header\n")
def test_import_file_unknown_csv(mock_file, mock_splitext, mock_import_service, capsys):
    args = argparse.Namespace(
        verb="import",
        import_type="file",
        file="unknown.csv",
        collection="COL123",
        verbose=True,
        user=False
    )

    ImportCommand().execute(args)
    out = capsys.readouterr().out
    assert "Error: Unknown CSV format" in out


@patch("builtins.open", new_callable=mock_open, read_data="arxiv query string\n")
def test_import_arxiv_file(mock_file, mock_import_service, capsys):
    args = argparse.Namespace(
        verb="import",
        import_type="arxiv",
        query=None,
        file="query.txt",
        limit=10,
        collection="COL123",
        verbose=True,
        user=False
    )
    mock_import_service.import_papers.return_value = 10

    with patch("zotero_cli.infra.factory.GatewayFactory.get_arxiv_gateway"):
        strategy_mock = MagicMock()
        strategy_mock.fetch_papers.return_value = []
        with patch("zotero_cli.core.strategies.ArxivImportStrategy", return_value=strategy_mock):
            ImportCommand().execute(args)

    out = capsys.readouterr().out
    assert "Imported 10 items." in out


def test_import_arxiv_parsed(mock_import_service, capsys):
    # test query parser DSL (contains ';')
    args = argparse.Namespace(
        verb="import",
        import_type="arxiv",
        query="ti:machine learning; max_results: 5",
        file=None,
        limit=10,
        collection="COL123",
        verbose=True,
        user=False
    )
    mock_import_service.import_papers.return_value = 5

    with patch("zotero_cli.infra.factory.GatewayFactory.get_arxiv_gateway"):
        strategy_mock = MagicMock()
        strategy_mock.fetch_papers.return_value = []
        with patch("zotero_cli.core.strategies.ArxivImportStrategy", return_value=strategy_mock):
            ImportCommand().execute(args)

    out = capsys.readouterr().out
    assert "Imported 5 items." in out


def test_import_bdtd(mock_import_service, capsys):
    args = argparse.Namespace(
        verb="import",
        import_type="bdtd",
        identifier="12345",
        collection="COL123",
        verbose=True,
        user=False
    )
    mock_import_service.import_papers.return_value = 1

    mock_client = MagicMock()
    mock_paper = MagicMock()
    mock_paper.title = "Thesis Title"
    mock_paper.authors = ["Author One"]
    mock_paper.publication = "Uni"
    mock_paper.year = "2025"
    mock_paper.extra = "Extra info"
    mock_paper.pdf_url = "http://uni.edu/thesis.pdf"
    mock_client.get_paper_metadata.return_value = mock_paper

    with patch("zotero_cli.infra.factory.GatewayFactory.get_bdtd_client", return_value=mock_client):
        ImportCommand().execute(args)

    out = capsys.readouterr().out
    assert "Title: Thesis Title" in out
    assert "University: Uni" in out
    assert "Imported 1 thesis item(s)." in out
