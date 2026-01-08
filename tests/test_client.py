import pytest
from unittest.mock import Mock
from zotero_cli.client import PaperImporterClient, CollectionNotFoundError
from zotero_cli.core.interfaces import (
    ZoteroGateway, ArxivGateway, BibtexGateway, 
    RisGateway, SpringerCsvGateway, IeeeCsvGateway
)
from zotero_cli.core.models import ResearchPaper

@pytest.fixture
def mock_zotero_gateway():
    return Mock(spec=ZoteroGateway)

@pytest.fixture
def mock_arxiv_gateway():
    return Mock(spec=ArxivGateway)

@pytest.fixture
def mock_bibtex_gateway():
    return Mock(spec=BibtexGateway)

@pytest.fixture
def mock_ris_gateway():
    return Mock(spec=RisGateway)

@pytest.fixture
def mock_springer_csv_gateway():
    return Mock(spec=SpringerCsvGateway)

@pytest.fixture
def mock_ieee_csv_gateway():
    return Mock(spec=IeeeCsvGateway)

@pytest.fixture
def client(
    mock_zotero_gateway, 
    mock_arxiv_gateway,
    mock_bibtex_gateway,
    mock_ris_gateway,
    mock_springer_csv_gateway,
    mock_ieee_csv_gateway
):
    return PaperImporterClient(
        zotero_gateway=mock_zotero_gateway,
        arxiv_gateway=mock_arxiv_gateway,
        bibtex_gateway=mock_bibtex_gateway,
        ris_gateway=mock_ris_gateway,
        springer_csv_gateway=mock_springer_csv_gateway,
        ieee_csv_gateway=mock_ieee_csv_gateway
    )

def test_add_paper_success(client, mock_zotero_gateway):
    mock_zotero_gateway.get_collection_id_by_name.return_value = "COLL_123"
    mock_zotero_gateway.create_item.return_value = True

    result = client.add_paper("2301.00001", "Test Abstract", "Test Title", "My Folder")

    assert result is True
    mock_zotero_gateway.get_collection_id_by_name.assert_called_with("My Folder")
    mock_zotero_gateway.create_item.assert_called_once()

def test_add_paper_create_collection(client, mock_zotero_gateway):
    mock_zotero_gateway.get_collection_id_by_name.return_value = None
    mock_zotero_gateway.create_collection.return_value = "NEW_COLL_KEY"
    mock_zotero_gateway.create_item.return_value = True

    result = client.add_paper("2301.00001", "Abs", "Title", "New Folder")

    assert result is True
    mock_zotero_gateway.get_collection_id_by_name.assert_called_with("New Folder")
    mock_zotero_gateway.create_collection.assert_called_with("New Folder")
    mock_zotero_gateway.create_item.assert_called_once()
    args, _ = mock_zotero_gateway.create_item.call_args
    assert args[1] == "NEW_COLL_KEY"

def test_add_paper_collection_creation_fails(client, mock_zotero_gateway):
    mock_zotero_gateway.get_collection_id_by_name.return_value = None
    mock_zotero_gateway.create_collection.return_value = None

    with pytest.raises(CollectionNotFoundError):
        client.add_paper("2301.00001", "Abs", "Title", "Fail Folder")

def test_import_from_query_success(client, mock_zotero_gateway, mock_arxiv_gateway):
    mock_zotero_gateway.get_collection_id_by_name.return_value = "COLL_456"
    mock_zotero_gateway.create_item.return_value = True
    
    mock_papers = [
        ResearchPaper(title="P1", abstract="A1"), 
        ResearchPaper(title="P2", abstract="A2")
    ]
    mock_arxiv_gateway.search.return_value = iter(mock_papers)

    count = client.import_from_query("q", "F", 2)
    assert count == 2

def test_import_from_query_partial_failure(client, mock_zotero_gateway, mock_arxiv_gateway):
    mock_zotero_gateway.get_collection_id_by_name.return_value = "C"
    mock_papers = [ResearchPaper(title="P1", abstract="A1"), ResearchPaper(title="P2", abstract="A2")]
    mock_arxiv_gateway.search.return_value = iter(mock_papers)
    # Success for P1, Failure for P2
    mock_zotero_gateway.create_item.side_effect = [True, False]

    count = client.import_from_query("q", "F")
    assert count == 1

def test_import_from_bibtex_success(client, mock_zotero_gateway, mock_bibtex_gateway):
    mock_zotero_gateway.get_collection_id_by_name.return_value = "C"
    mock_papers = [ResearchPaper(title="B1", abstract="AB1")]
    mock_bibtex_gateway.parse_file.return_value = iter(mock_papers)
    mock_zotero_gateway.create_item.return_value = True

    count = client.import_from_bibtex("f.bib", "F")
    assert count == 1

def test_import_from_springer_csv_success(client, mock_zotero_gateway, mock_springer_csv_gateway):
    mock_zotero_gateway.get_collection_id_by_name.return_value = "C"
    mock_papers = [ResearchPaper(title="S1", abstract="AS1")]
    mock_springer_csv_gateway.parse_file.return_value = iter(mock_papers)
    mock_zotero_gateway.create_item.return_value = True

    count = client.import_from_springer_csv("f.csv", "F")
    assert count == 1

def test_remove_attachments_success(client, mock_zotero_gateway):
    mock_zotero_gateway.get_collection_id_by_name.return_value = "C"
    mock_item = Mock()
    mock_item.key = "K1"
    mock_zotero_gateway.get_items_in_collection.return_value = iter([mock_item])
    
    mock_child = {
        'key': 'AK1', 
        'version': 1, 
        'data': {'itemType': 'attachment', 'title': 'PDF'}
    }
    mock_zotero_gateway.get_item_children.return_value = [mock_child]
    mock_zotero_gateway.delete_item.return_value = True

    count = client.remove_attachments_from_folder("F")
    assert count == 1
    mock_zotero_gateway.delete_item.assert_called_with("AK1", 1)

def test_remove_attachments_collection_not_found(client, mock_zotero_gateway):
    mock_zotero_gateway.get_collection_id_by_name.return_value = None
    with pytest.raises(CollectionNotFoundError):
        client.remove_attachments_from_folder("Missing")

def test_import_from_ris_success(client, mock_zotero_gateway, mock_ris_gateway):
    mock_zotero_gateway.get_collection_id_by_name.return_value = "COLL_RIS"
    mock_zotero_gateway.create_item.return_value = True

    mock_ris_papers = [
        ResearchPaper(title="RIS Paper 1", abstract="RIS Abs 1"),
        ResearchPaper(title="RIS Paper 2", abstract="RIS Abs 2"),
    ]
    mock_ris_gateway.parse_file.return_value = iter(mock_ris_papers)

    imported_count = client.import_from_ris("test.ris", "RIS Folder", verbose=False)

    assert imported_count == 2
    mock_zotero_gateway.get_collection_id_by_name.assert_called_with("RIS Folder")
    mock_ris_gateway.parse_file.assert_called_once_with("test.ris")
    assert mock_zotero_gateway.create_item.call_count == 2
    
    calls = mock_zotero_gateway.create_item.call_args_list
    assert calls[0].args[0] == mock_ris_papers[0]
    assert calls[0].args[1] == "COLL_RIS"
    assert calls[1].args[0] == mock_ris_papers[1]
    assert calls[1].args[1] == "COLL_RIS"

def test_import_from_ris_ris_gateway_not_provided(mock_zotero_gateway):
    client_no_ris = PaperImporterClient(zotero_gateway=mock_zotero_gateway)
    with pytest.raises(ValueError):
        client_no_ris.import_from_ris("test.ris", "Some Folder")

def test_import_from_ieee_csv_success(client, mock_zotero_gateway, mock_ieee_csv_gateway):
    mock_zotero_gateway.get_collection_id_by_name.return_value = "COLL_IEEE"
    mock_zotero_gateway.create_item.return_value = True

    mock_ieee_papers = [
        ResearchPaper(title="IEEE Paper 1", abstract="IEEE Abs 1", authors=["Author A"]),
        ResearchPaper(title="IEEE Paper 2", abstract="IEEE Abs 2", authors=["Author B"]),
    ]
    mock_ieee_csv_gateway.parse_file.return_value = iter(mock_ieee_papers)

    imported_count = client.import_from_ieee_csv("test.csv", "IEEE Folder", verbose=False)

    assert imported_count == 2
    mock_zotero_gateway.get_collection_id_by_name.assert_called_with("IEEE Folder")
    mock_ieee_csv_gateway.parse_file.assert_called_once_with("test.csv")
    assert mock_zotero_gateway.create_item.call_count == 2
    
    calls = mock_zotero_gateway.create_item.call_args_list
    assert calls[0].args[0] == mock_ieee_papers[0]
    assert calls[0].args[1] == "COLL_IEEE"
    assert calls[1].args[0] == mock_ieee_papers[1]
    assert calls[1].args[1] == "COLL_IEEE"

def test_import_from_ieee_csv_ieee_csv_gateway_not_provided(mock_zotero_gateway):
    client_no_ieee_csv = PaperImporterClient(zotero_gateway=mock_zotero_gateway)
    with pytest.raises(ValueError):
        client_no_ieee_csv.import_from_ieee_csv("test.csv", "Some Folder")
