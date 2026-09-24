"""item hydrate (Issue #344): any identifier, aggregator lookups, fill-empty
by default, preview unless execute."""

from unittest.mock import Mock

import pytest

from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.services.enrichment_service import (
    DEFAULT_FIELDS,
    EnrichmentService,
    parse_fields,
)
from zotero_cli.core.zotero_item import ZoteroItem

# The Zotero Web API returns every field valid for the item type, empty or
# not; hydrate only writes fields present here.
JOURNAL_FIELDS = {
    "itemType": "journalArticle",
    "title": "",
    "abstractNote": "",
    "date": "",
    "publicationTitle": "",
    "DOI": "",
    "url": "",
    "creators": [],
    "extra": "",
}


def _item(key="K1", **data):
    fields = dict(JOURNAL_FIELDS)
    fields.update(data)
    return ZoteroItem.from_raw_zotero_item({"key": key, "data": {"version": 3, **fields}})


def _paper(**kw):
    base: dict = dict(
        title="Deep learning",
        abstract="An abstract.",
        doi="10.1038/nature14539",
        year="2015",
        publication="Nature",
        url="https://doi.org/10.1038/nature14539",
        authors=["Yann LeCun", "Yoshua Bengio", "Geoffrey Hinton"],
    )
    base.update(kw)
    return ResearchPaper(**base)


@pytest.fixture
def repo():
    r = Mock()
    r.update_item.return_value = True
    return r


@pytest.fixture
def arxiv():
    return Mock()


@pytest.fixture
def aggregator():
    return Mock()


@pytest.fixture
def searcher():
    return Mock()


@pytest.fixture
def service(repo, arxiv, aggregator, searcher):
    return EnrichmentService(repo, repo, arxiv, aggregator, searcher)


def test_non_arxiv_doi_item_gets_empty_fields_proposed(service, aggregator, repo):
    """Acceptance: a journal article with a DOI but no abstract is covered,
    not just arXiv items."""
    aggregator.get_enriched_metadata.return_value = _paper()
    item = _item(title="Deep learning", DOI="10.1038/nature14539")

    result = service.hydrate(item)

    assert result.status == "proposed"
    assert result.identifier == "doi:10.1038/nature14539"
    assert result.changes["abstractNote"] == {"old": "", "new": "An abstract."}
    assert result.changes["publicationTitle"]["new"] == "Nature"
    assert result.changes["date"]["new"] == "2015"
    assert result.changes["creators"]["new"][0] == {
        "creatorType": "author",
        "firstName": "Yann",
        "lastName": "LeCun",
    }
    assert "DOI" not in result.changes  # already set
    assert "title" not in result.changes  # never by default
    repo.update_item.assert_not_called()  # preview by default
    aggregator.get_enriched_metadata.assert_called_once_with(
        "10.1038/nature14539", require_doi_match=True
    )


def test_execute_writes_exactly_the_proposed_changes(service, aggregator, repo):
    aggregator.get_enriched_metadata.return_value = _paper()
    item = _item(DOI="10.1038/nature14539")

    result = service.hydrate(item, execute=True)

    assert result.status == "updated"
    key, version, payload = repo.update_item.call_args.args
    assert (key, version) == ("K1", 3)
    assert payload == {name: change["new"] for name, change in result.changes.items()}


def test_existing_values_are_kept_by_default(service, aggregator):
    """Acceptance: no existing non-empty field is overwritten by default."""
    aggregator.get_enriched_metadata.return_value = _paper()
    item = _item(
        DOI="10.1038/nature14539",
        abstractNote="My own abstract",
        date="2015-05-28",
        publicationTitle="Nature (London)",
    )

    result = service.hydrate(item)

    assert "abstractNote" not in result.changes
    assert "date" not in result.changes
    assert "publicationTitle" not in result.changes


def test_overwrite_replaces_values_but_not_the_title_or_a_fuller_date(service, aggregator):
    aggregator.get_enriched_metadata.return_value = _paper(title="Deep Learning (updated)")
    item = _item(
        title="Deep learning",
        DOI="10.1038/nature14539",
        abstractNote="Old abstract",
        date="2015-05-28",
    )

    result = service.hydrate(item, overwrite=True)

    assert result.changes["abstractNote"] == {"old": "Old abstract", "new": "An abstract."}
    assert "date" not in result.changes  # same year: keep the full date
    assert "title" not in result.changes  # only when named in --fields

    titled = service.hydrate(item, overwrite=True, fields=("title",))
    assert titled.changes == {
        "title": {"old": "Deep learning", "new": "Deep Learning (updated)"}
    }


def test_fields_restriction(service, aggregator):
    aggregator.get_enriched_metadata.return_value = _paper()
    result = service.hydrate(_item(DOI="10.1038/nature14539"), fields=("abstract",))
    assert list(result.changes) == ["abstractNote"]


def test_fields_invalid_for_the_item_type_are_never_proposed(service, aggregator):
    """A book has no publicationTitle/DOI field in this schema: writing one
    would be rejected by Zotero."""
    aggregator.get_enriched_metadata.return_value = _paper()
    book = ZoteroItem.from_raw_zotero_item(
        {
            "key": "B1",
            "data": {
                "itemType": "book",
                "title": "Deep learning",
                "abstractNote": "",
                "date": "",
                "extra": "",
                "creators": [],
                "url": "",
                "DOI": "10.1038/nature14539",
            },
        }
    )
    result = service.hydrate(book)
    assert "publicationTitle" not in result.changes
    assert set(result.changes) <= {"abstractNote", "date", "creators", "url"}


def test_venue_uses_the_item_types_own_field(service, aggregator):
    aggregator.get_enriched_metadata.return_value = _paper(publication="Proc. CHI")
    paper = ZoteroItem.from_raw_zotero_item(
        {
            "key": "C1",
            "data": {
                "itemType": "conferencePaper",
                "title": "T",
                "proceedingsTitle": "",
                "conferenceName": "",
                "DOI": "10.1145/1",
                "extra": "",
            },
        }
    )
    result = service.hydrate(paper, fields=("venue",))
    assert result.changes == {"proceedingsTitle": {"old": "", "new": "Proc. CHI"}}


def test_arxiv_item_gets_published_doi_and_journal(service, arxiv, aggregator):
    """Acceptance: the original arXiv behavior still works."""
    arxiv.search.return_value = iter(
        [_paper(doi="10.1145/3442188.3445922", publication="FAccT", abstract="")]
    )
    aggregator.get_enriched_metadata.return_value = _paper(
        doi="10.1145/3442188.3445922", publication=None, abstract="From providers"
    )
    item = _item(title="On the dangers...", extra="arXiv: 2103.10433")

    result = service.hydrate(item)

    assert result.identifier == "arxiv:2103.10433"
    assert result.changes["DOI"]["new"] == "10.1145/3442188.3445922"
    assert result.changes["publicationTitle"]["new"] == "FAccT"  # from arXiv
    assert result.changes["abstractNote"]["new"] == "From providers"
    arxiv.search.assert_called_once_with("id:2103.10433", max_results=1)
    aggregator.get_enriched_metadata.assert_called_once_with(
        "10.1145/3442188.3445922", require_doi_match=True
    )


def test_arxiv_preprint_not_yet_published_uses_arxiv_metadata(service, arxiv, aggregator):
    arxiv.search.return_value = iter([_paper(doi=None, publication=None)])
    result = service.hydrate(_item(extra="arXiv: 2401.00001"), fields=("abstract",))
    assert result.source == "arXiv"
    assert result.changes["abstractNote"]["new"] == "An abstract."
    aggregator.get_enriched_metadata.assert_not_called()


def test_pmid_in_extra_is_used(service, aggregator):
    aggregator.get_enriched_metadata.return_value = _paper()
    result = service.hydrate(_item(extra="Some note\nPMID: 26017442\n"))
    assert result.identifier == "pmid:26017442"
    aggregator.get_enriched_metadata.assert_called_once_with("26017442")


def test_item_without_identifier_is_reported_not_guessed(service, aggregator, searcher):
    """Acceptance: items without identifiers."""
    result = service.hydrate(_item(title="Some paper"))
    assert result.status == "no-identifier"
    assert "--by-title" in (result.message or "")
    aggregator.get_enriched_metadata.assert_not_called()
    searcher.search.assert_not_called()


def test_by_title_accepts_only_a_confident_match(service, aggregator, searcher):
    item = _item(
        title="Deep Learning",
        date="2015",
        creators=[{"creatorType": "author", "firstName": "Yann", "lastName": "LeCun"}],
    )
    searcher.search.return_value = iter(
        [
            _paper(title="Deep learning for everyone"),  # different title
            _paper(title="Deep learning", year="2019"),  # different year
            _paper(title="Deep learning", authors=["Someone Else"]),  # different author
            _paper(title="Deep learning."),  # the match (punctuation ignored)
        ]
    )
    aggregator.get_enriched_metadata.return_value = _paper()

    result = service.hydrate(item, by_title=True)

    assert result.identifier == "title"
    assert result.status == "proposed"
    aggregator.get_enriched_metadata.assert_called_once_with(
        "10.1038/nature14539", require_doi_match=True
    )


def test_by_title_without_a_confident_match_is_not_found(service, searcher):
    searcher.search.return_value = iter([_paper(title="Something else")])
    result = service.hydrate(_item(title="Deep learning"), by_title=True)
    assert result.status == "not-found"
    assert result.changes == {}


def test_doi_mismatch_candidates_never_reach_the_item(service, aggregator):
    """Acceptance: DOI-mismatch rejection. The aggregator filters
    mismatching candidates (#340); when nothing is left it returns None."""
    aggregator.get_enriched_metadata.return_value = None
    result = service.hydrate(_item(DOI="10.1145/3290605.3300233"))
    assert result.status == "not-found"
    assert result.changes == {}


def test_failures_are_reported_per_item_not_raised(service, aggregator, repo):
    aggregator.get_enriched_metadata.side_effect = RuntimeError("provider down")
    result = service.hydrate(_item(DOI="10.1234/x"))
    assert result.status == "failed" and "provider down" in (result.message or "")

    aggregator.get_enriched_metadata.side_effect = None
    aggregator.get_enriched_metadata.return_value = _paper(doi="10.1234/x")
    repo.update_item.return_value = False
    rejected = service.hydrate(_item(DOI="10.1234/x"), execute=True)
    assert rejected.status == "failed"


def test_collection_and_all_skip_children_and_attachments(service, repo, aggregator):
    aggregator.get_enriched_metadata.return_value = _paper()
    work = _item("W1", DOI="10.1038/nature14539")
    attachment = ZoteroItem(key="A1", version=1, item_type="attachment")
    child_note = ZoteroItem(key="N1", version=1, item_type="note", parent_item="W1")
    repo.get_items_in_collection.return_value = iter([work, attachment, child_note])
    repo.get_all_items.return_value = iter([work, attachment])

    in_collection = service.hydrate_collection("COL")
    in_library = service.hydrate_all()

    assert [r.key for r in in_collection] == ["W1"]
    assert [r.key for r in in_library] == ["W1"]
    repo.get_items_in_collection.assert_called_once_with("COL", top_only=True)
    repo.get_all_items.assert_called_once()  # client-side scan, no q="arxiv.org"


def test_result_serializes_for_json_output(service, aggregator):
    aggregator.get_enriched_metadata.return_value = _paper()
    data = service.hydrate(_item(DOI="10.1038/nature14539"), fields=("abstract",)).to_dict()
    assert data == {
        "key": "K1",
        "title": "Untitled",
        "status": "proposed",
        "identifier": "doi:10.1038/nature14539",
        "source": "metadata providers",
        "changes": {"abstractNote": {"old": "", "new": "An abstract."}},
        "message": None,
    }


def test_parse_fields():
    assert parse_fields(None) == DEFAULT_FIELDS
    assert parse_fields(" Abstract, venue ") == ("abstract", "venue")
    with pytest.raises(ValueError, match="volume"):
        parse_fields("abstract,volume")


def test_url_prefers_the_doi_resolver(service, aggregator):
    aggregator.get_enriched_metadata.return_value = _paper(
        url="https://pubmed.ncbi.nlm.nih.gov/26017442/"
    )
    result = service.hydrate(_item(DOI="10.1038/nature14539"), fields=("url",))
    assert result.changes["url"]["new"] == "https://doi.org/10.1038/nature14539"
