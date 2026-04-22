from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.infra.pubmed_api import PubMedAPIClient


@pytest.fixture
def client():
    return PubMedAPIClient(api_key="test_key")

def test_apply_rate_limit(client):
    import time
    client.last_request_time = time.time()
    # Should sleep briefly. We just verify it doesn't crash
    client._apply_rate_limit()
    assert client.last_request_time > 0

def test_resolve_pmcid_to_pmid_success(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "records": [{"pmcid": "PMC123", "pmid": "456"}]
    }

    with patch("requests.get", return_value=mock_response):
        pmid = client._resolve_pmcid_to_pmid("PMC123")
        assert pmid == "456"

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
