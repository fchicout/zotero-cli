from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.infra.pubmed_api import PubMedAPIClient


@pytest.fixture
def client():
    return PubMedAPIClient(api_key="test_key")


def test_pacing_follows_the_api_key_3_requests_a_second_without_10_with():
    assert PubMedAPIClient().min_request_interval == 0.34
    assert PubMedAPIClient(api_key="k").min_request_interval == 0.1


def test_back_to_back_requests_are_paced(client):
    with patch("zotero_cli.core.utils.host_throttle.time.sleep") as sleep:
        client._apply_rate_limit()
        client._apply_rate_limit()

    sleep.assert_called_once()
    assert 0 < sleep.call_args[0][0] <= 0.1


def _json_response(payload, status=200, headers=None):
    import json

    import requests

    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(payload).encode()
    response.headers.update(headers or {})
    return response


def test_resolve_pmcid_to_pmid_success(client):
    response = _json_response({"records": [{"pmcid": "PMC123", "pmid": "456"}]})

    with patch.object(client.session, "get", return_value=response) as get:
        pmid = client._resolve_pmcid_to_pmid("PMC123")

    assert pmid == "456"
    url = get.call_args.args[0]
    assert url == "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
    params = get.call_args.kwargs["params"]
    assert params["ids"] == "PMC123"
    assert "api_key" not in params  # idconv doesn't take one


def test_the_pmcid_lookup_is_paced_like_every_other_ncbi_request(client):
    """Issue #713: it used to be a bare requests.get."""
    response = _json_response({"records": [{"pmid": "456"}]})

    with (
        patch.object(client.session, "get", return_value=response),
        patch.object(client, "_apply_rate_limit") as pace,
    ):
        client._resolve_pmcid_to_pmid("PMC123")

    pace.assert_called_once_with()


def test_the_pmcid_lookup_waits_out_a_429_and_retries(client):
    limited = _json_response({}, status=429, headers={"Retry-After": "1"})
    answered = _json_response({"records": [{"pmid": "456"}]})

    with (
        patch.object(client.session, "get", side_effect=[limited, answered]) as get,
        patch("zotero_cli.infra.base_api_client.time.sleep") as sleep,
    ):
        pmid = client._resolve_pmcid_to_pmid("PMC123")

    assert pmid == "456"
    assert get.call_count == 2
    sleep.assert_any_call(1.0)


def test_get_paper_metadata_paces_a_pmcid_once(client):
    """The pacing moved into the request, so the caller no longer adds its own."""
    with (
        patch.object(client, "_resolve_pmcid_to_pmid", return_value=None) as resolve,
        patch.object(client, "_apply_rate_limit") as pace,
    ):
        assert client.get_paper_metadata("PMC123") is None

    resolve.assert_called_once_with("PMC123")
    pace.assert_not_called()


def test_parse_pubmed_xml(client):
    xml_content = """
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>12345</PMID>
          <Article>
            <Journal>
              <Title>Nature Medicine</Title>
              <JournalIssue>
                <PubDate><Year>2023</Year></PubDate>
              </JournalIssue>
            </Journal>
            <ArticleTitle>Test PubMed Paper</ArticleTitle>
            <Abstract>
              <AbstractText Label="OBJECTIVE">To test.</AbstractText>
              <AbstractText Label="RESULTS">It works.</AbstractText>
            </Abstract>
            <AuthorList>
              <Author>
                <LastName>Doe</LastName>
                <ForeName>John</ForeName>
              </Author>
            </AuthorList>
          </Article>
        </MedlineCitation>
        <PubmedData>
          <ArticleIdList>
            <ArticleId IdType="doi">10.1038/s123</ArticleId>
          </ArticleIdList>
        </PubmedData>
      </PubmedArticle>
    </PubmedArticleSet>
    """
    paper = client._parse_pubmed_xml(xml_content)
    assert paper.title == "Test PubMed Paper"
    assert "OBJECTIVE: To test." in paper.abstract
    assert "RESULTS: It works." in paper.abstract
    assert paper.authors == ["John Doe"]
    assert paper.publication == "Nature Medicine"
    assert paper.year == "2023"
    assert paper.doi == "10.1038/s123"
    assert paper.url == "https://pubmed.ncbi.nlm.nih.gov/12345/"


def test_get_paper_metadata_pmid(client):
    mock_response = MagicMock()
    mock_response.text = "<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID></MedlineCitation></PubmedArticle></PubmedArticleSet>"

    with patch.object(client, "_get", return_value=mock_response):
        with patch.object(client, "_parse_pubmed_xml") as mock_parse:
            client.get_paper_metadata("1")
            mock_parse.assert_called_once()


def test_get_paper_metadata_pmcid(client):
    mock_response = MagicMock()
    mock_response.text = "xml"

    with patch.object(client, "_resolve_pmcid_to_pmid", return_value="1"):
        with patch.object(client, "_get", return_value=mock_response):
            client.get_paper_metadata("PMC123")
            client._resolve_pmcid_to_pmid.assert_called_with("PMC123")


def _article_xml(doi):
    return (
        "<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>26017442</PMID>"
        "<Article><ArticleTitle>Deep learning</ArticleTitle></Article></MedlineCitation>"
        f'<PubmedData><ArticleIdList><ArticleId IdType="doi">{doi}</ArticleId>'
        "</ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>"
    )


def test_doi_is_resolved_with_esearch_not_sent_to_efetch_as_an_id(client):
    """Issue #340: efetch?id=10.1145/... returned PMID 10, an unrelated
    1970s paper, whose title then won the merge."""
    esearch = MagicMock()
    esearch.json.return_value = {"esearchresult": {"idlist": ["26017442"]}}
    efetch = MagicMock(text=_article_xml("10.1038/nature14539"))

    with patch.object(client, "_get", side_effect=[esearch, efetch]) as get:
        paper = client.get_paper_metadata("10.1038/nature14539")

    assert paper is not None
    assert paper.title == "Deep learning"
    search_call, fetch_call = get.call_args_list
    assert search_call.kwargs["endpoint"] == "esearch.fcgi"
    assert search_call.kwargs["params"]["term"] == '"10.1038/nature14539"[doi]'
    assert fetch_call.kwargs["params"]["id"] == "26017442"


def test_doi_not_indexed_in_pubmed_returns_none_without_efetch(client):
    esearch = MagicMock()
    esearch.json.return_value = {"esearchresult": {"idlist": []}}
    with patch.object(client, "_get", return_value=esearch) as get:
        assert client.get_paper_metadata("10.1145/3290605.3300233") is None
    assert get.call_count == 1  # never fetched a record


def test_record_with_a_different_doi_is_rejected(client):
    esearch = MagicMock()
    esearch.json.return_value = {"esearchresult": {"idlist": ["10"]}}
    efetch = MagicMock(text=_article_xml("10.1016/0006-2952(75)90101-3"))
    with patch.object(client, "_get", side_effect=[esearch, efetch]):
        assert client.get_paper_metadata("10.1145/3290605.3300233") is None


@pytest.mark.parametrize("identifier", ["arXiv:1706.03762", "not an id", "10.1145", ""])
def test_unrecognised_identifiers_make_no_request(client, identifier):
    with patch.object(client, "_get") as get, patch.object(client.session, "get") as raw_get:
        assert client.get_paper_metadata(identifier) is None
    get.assert_not_called()
    raw_get.assert_not_called()


def test_contact_email_is_the_users_own_and_only_when_configured():
    """Issue #337: no built-in maintainer address in NCBI requests."""
    anonymous = PubMedAPIClient()
    assert anonymous._ncbi_params() == {"tool": "zotero-cli"}
    configured = PubMedAPIClient(api_key="k", contact_email="me@example.org")
    assert configured._ncbi_params() == {
        "tool": "zotero-cli",
        "email": "me@example.org",
        "api_key": "k",
    }
