from zotero_cli.core.services.slr.citation_service import CitationService
from zotero_cli.core.zotero_item import ZoteroItem


def test_resolve_citation_key_from_extra():
    svc = CitationService()

    # 1. Matching 'Citation Key: foo123'
    item1 = ZoteroItem.from_raw_zotero_item({
        "key": "K1",
        "data": {
            "title": "T1",
            "extra": "Citation Key: foo123\nother extra stuff",
            "creators": []
        }
    })
    assert svc.resolve_citation_key(item1) == "foo123"

    # 2. Case insensitivity check 'citation key: BAR-456'
    item2 = ZoteroItem.from_raw_zotero_item({
        "key": "K2",
        "data": {
            "title": "T2",
            "extra": "some line\ncitation key: BAR-456",
            "creators": []
        }
    })
    assert svc.resolve_citation_key(item2) == "BAR-456"


def test_resolve_citation_key_fallback_generation():
    svc = CitationService()

    # Author with lastName and valid year
    item1 = ZoteroItem.from_raw_zotero_item({
        "key": "K1",
        "data": {
            "title": "T1",
            "date": "2026-03-18",
            "creators": [
                {"creatorType": "editor", "lastName": "Smith"},
                {"creatorType": "author", "lastName": "Chicout"}
            ]
        }
    })
    assert svc.resolve_citation_key(item1) == "Chicout2026"

    # Author with name (no lastName) and clean name check, no valid year (n.d.)
    item2 = ZoteroItem.from_raw_zotero_item({
        "key": "K2",
        "data": {
            "title": "T2",
            "date": "unknown date",
            "creators": [
                {"creatorType": "author", "name": "O'Connor"}
            ]
        }
    })
    # O'Connor -> OConnor
    assert svc.resolve_citation_key(item2) == "OConnorn.d."

    # Unknown author (no creators) and year matching
    item3 = ZoteroItem.from_raw_zotero_item({
        "key": "K3",
        "data": {
            "title": "T3",
            "date": "1999",
            "creators": []
        }
    })
    assert svc.resolve_citation_key(item3) == "Unknown1999"
