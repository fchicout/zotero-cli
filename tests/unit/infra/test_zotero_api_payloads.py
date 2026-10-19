import dataclasses
from typing import Any

from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.zotero_api import ZoteroAPIClient


def _paper(**overrides: Any) -> ResearchPaper:
    base = ResearchPaper(title="T", abstract="A", authors=["Ada Lovelace", "Plato"], doi="10.1/x")
    return dataclasses.replace(base, **overrides)


def test_authors_split_on_the_last_space_and_a_single_name_stays_whole() -> None:
    assert ZoteroAPIClient._creators_payload(_paper()) == [
        {"creatorType": "author", "firstName": "Ada", "lastName": "Lovelace"},
        {"creatorType": "author", "name": "Plato"},
    ]


def test_an_arxiv_article_payload_carries_the_url_catalog_and_extra() -> None:
    paper = _paper(arxiv_id="1706.03762", extra="Note", year="2017", publication="NeurIPS")
    creators = ZoteroAPIClient._creators_payload(paper)

    payload = ZoteroAPIClient._build_article_payload(paper, creators, "COLL")

    assert payload == {
        "itemType": "journalArticle",
        "title": "T",
        "abstractNote": "A",
        "creators": creators,
        "collections": ["COLL"],
        "url": "https://arxiv.org/abs/1706.03762",
        "libraryCatalog": "arXiv",
        "extra": "arXiv: 1706.03762\nNote",
        "DOI": "10.1/x",
        "publicationTitle": "NeurIPS",
        "date": "2017",
    }


def test_an_explicit_url_wins_and_empty_optional_fields_are_left_out() -> None:
    paper = _paper(url="https://example.org/p", doi=None)

    payload = ZoteroAPIClient._build_article_payload(paper, [], "COLL")

    assert payload["url"] == "https://example.org/p"
    assert set(payload) == {"itemType", "title", "abstractNote", "creators", "collections", "url"}
