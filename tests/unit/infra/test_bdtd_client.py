from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.infra.bdtd_api import BDTDAPIClient


@pytest.fixture
def client():
    return BDTDAPIClient()


# -- Mapping Tests -----------------------------------------------------------------


def test_map_to_research_paper_full(client):
    """Test full metadata mapping from a BDTD VuFind record."""
    record = {
        "id": "UFMA_4bd0f7827d06b3ce2d77cabaf6f35327",
        "title": "Inteligência Artificial aplicada à educação",
        "authors": {
            "primary": {"Silva, Maria da": {}},
            "secondary": {"Santos, João dos": {}},
        },
        "urls": [
            {"url": "https://tedebc.ufma.br/jspui/handle/tede/6900", "desc": "Acesso ao documento"}
        ],
        "summary": ["Resumo da tese sobre IA na educação.", "Segundo parágrafo do resumo."],
        "publicationDates": ["2023"],
        "institutions": ["Universidade Federal do Maranhão"],
        "formats": ["masterThesis"],
        "languages": ["por"],
        "subjects": [["Inteligência Artificial"], ["Educação"]],
    }

    paper = client._map_to_research_paper(record)

    assert paper.title == "Inteligência Artificial aplicada à educação"
    assert "Silva, Maria da" in paper.authors
    assert "Santos, João dos" in paper.authors
    assert paper.year == "2023"
    assert paper.publication == "Universidade Federal do Maranhão"
    assert paper.url == "https://tedebc.ufma.br/jspui/handle/tede/6900"
    assert "Resumo da tese sobre IA na educação." in paper.abstract
    assert "Segundo parágrafo do resumo." in paper.abstract
    assert paper.extra is not None
    assert "Degree Level: masterThesis" in paper.extra
    assert "Languages: por" in paper.extra
    assert "Subjects: Inteligência Artificial, Educação" in paper.extra


def test_map_to_research_paper_minimal(client):
    """Test mapping with minimal/missing fields."""
    record = {
        "title": "Tese Mínima",
        "authors": {},
        "urls": [],
        "summary": [],
    }

    paper = client._map_to_research_paper(record)

    assert paper.title == "Tese Mínima"
    assert paper.authors == []
    assert paper.abstract == ""
    assert paper.year is None
    assert paper.publication is None
    assert paper.url is None
    assert paper.doi is None


def test_map_to_research_paper_doi_in_urls(client):
    """Test DOI extraction when doi.org link is present in urls."""
    record = {
        "title": "Tese com DOI",
        "authors": {"primary": {"Souza, Ana": {}}},
        "urls": [
            {"url": "https://repositorio.pucrio.br/handle/123", "desc": ""},
            {"url": "https://doi.org/10.17771/PUCRio.acad.55901", "desc": "DOI"},
        ],
    }

    paper = client._map_to_research_paper(record)

    assert paper.doi == "10.17771/PUCRio.acad.55901"
    # URL should be the first url in the list
    assert paper.url == "https://repositorio.pucrio.br/handle/123"


def test_map_to_research_paper_authors_list_format(client):
    """Test authors when they arrive as a list instead of dict."""
    record = {
        "title": "Test Authors List",
        "authors": ["Author One", "Author Two"],
    }

    paper = client._map_to_research_paper(record)

    assert paper.authors == ["Author One", "Author Two"]


# -- get_paper_metadata Tests ------------------------------------------------------


def test_get_paper_metadata_by_direct_id(client):
    """Test lookup by direct BDTD record ID."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "records": [
            {
                "id": "UFMA_4bd0f7827d06b3ce2d77cabaf6f35327",
                "title": "Tese Encontrada",
                "authors": {"primary": {"Autor, Teste": {}}},
                "urls": [],
            }
        ]
    }

    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("UFMA_4bd0f7827d06b3ce2d77cabaf6f35327")

        assert paper is not None
        assert paper.title == "Tese Encontrada"
        args, kwargs = client._get.call_args
        assert args[0] == "record"
        assert kwargs["params"]["id"] == "UFMA_4bd0f7827d06b3ce2d77cabaf6f35327"


def test_get_paper_metadata_by_prefixed_id(client):
    """Test lookup with bdtd: prefix."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "records": [
            {
                "id": "ABC_123",
                "title": "Prefixed Thesis",
                "authors": {},
                "urls": [],
            }
        ]
    }

    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("bdtd:ABC_123")

        assert paper is not None
        assert paper.title == "Prefixed Thesis"
        args, kwargs = client._get.call_args
        assert args[0] == "record"
        assert kwargs["params"]["id"] == "ABC_123"


def test_get_paper_metadata_by_handle_url(client):
    """Test lookup by handle URL triggers search endpoint."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "records": [
            {
                "title": "Handle Thesis",
                "authors": {"primary": {"Alguém, Ninguém": {}}},
                "urls": [{"url": "https://tedebc.ufma.br/jspui/handle/tede/6900"}],
            }
        ]
    }

    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("https://tedebc.ufma.br/jspui/handle/tede/6900")

        assert paper is not None
        assert paper.title == "Handle Thesis"
        args, kwargs = client._get.call_args
        assert args[0] == "search"
        assert kwargs["params"]["lookfor"] == "https://tedebc.ufma.br/jspui/handle/tede/6900"


def test_get_paper_metadata_by_doi(client):
    """Test lookup by DOI triggers search endpoint."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "records": [
            {
                "title": "DOI Thesis",
                "authors": {},
                "urls": [{"url": "https://doi.org/10.17771/PUCRio.acad.55901"}],
            }
        ]
    }

    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("10.17771/PUCRio.acad.55901")

        assert paper is not None
        args, kwargs = client._get.call_args
        assert args[0] == "search"


def test_get_paper_metadata_not_found(client):
    """Test that None is returned when no records are found."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"records": []}

    with patch.object(client, "_get", return_value=mock_response):
        paper = client.get_paper_metadata("nonexistent_id")
        assert paper is None


def test_get_paper_metadata_exception(client):
    """Test that None is returned on API errors."""
    with patch.object(client, "_get", side_effect=Exception("Connection error")):
        paper = client.get_paper_metadata("any_id")
        assert paper is None


# -- search Tests --------------------------------------------------------------------


def _bdtd_record(title: str, url: str = "https://repositorio.example/handle/1") -> dict:
    return {
        "title": title,
        "authors": {},
        "urls": [{"url": url}],
        "summary": [],
    }


def test_search_single_page(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "records": [_bdtd_record("Tese A"), _bdtd_record("Tese B")]
    }

    with patch.object(client, "_get", return_value=mock_response) as mock_get:
        results = list(client.search("aprendizado de maquina", max_results=2))

    assert len(results) == 2
    assert results[0].title == "Tese A"
    assert results[1].title == "Tese B"
    kwargs = mock_get.call_args.kwargs
    assert kwargs["params"]["lookfor"] == "aprendizado de maquina"
    assert kwargs["params"]["limit"] == 2


def test_search_does_not_resolve_pdf_urls(client):
    """The whole point of skipping resolve_pdf for bulk search results."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"records": [_bdtd_record("Tese A")]}

    with patch.object(client, "_get", return_value=mock_response):
        with patch.object(client, "_resolve_pdf_url_sync") as mock_resolve:
            results = list(client.search("topic", max_results=1))

    assert results[0].pdf_url is None
    mock_resolve.assert_not_called()


def test_search_paginates_until_max_results(client):
    page1 = MagicMock()
    page1.json.return_value = {"records": [_bdtd_record(f"T{i}") for i in range(20)]}
    page2 = MagicMock()
    page2.json.return_value = {"records": [_bdtd_record("T20"), _bdtd_record("T21")]}

    with patch.object(client, "_get", side_effect=[page1, page2]) as mock_get:
        results = list(client.search("topic", max_results=22))

    assert len(results) == 22
    assert mock_get.call_count == 2


def test_search_stops_on_empty_page(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"records": []}

    with patch.object(client, "_get", return_value=mock_response):
        results = list(client.search("no matches", max_results=10))

    assert results == []


def test_search_error_stops_iteration(client):
    with patch.object(client, "_get", side_effect=Exception("network error")):
        results = list(client.search("topic"))

    assert results == []
