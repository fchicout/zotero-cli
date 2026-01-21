from unittest.mock import Mock

import pytest

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.audit_service import CollectionAuditor
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return Mock(spec=ZoteroGateway)


@pytest.fixture
def auditor(mock_gateway):
    return CollectionAuditor(mock_gateway)


@pytest.fixture
def children_data():
    return {}


def create_mock_item(
    children_data, key, title=None, abstract=None, doi=None, arxiv_id=None, has_pdf=False
):
    raw_item = {
        "key": key,
        "data": {
            "version": 1,
            "itemType": "journalArticle",
            "title": title,
            "abstractNote": abstract,
            "DOI": doi,
            "extra": f"arXiv: {arxiv_id}" if arxiv_id else "",
        },
    }
    item = ZoteroItem.from_raw_zotero_item(raw_item)

    if has_pdf:
        children_data[key] = [
            {
                "key": "ATT" + key,
                "data": {
                    "itemType": "attachment",
                    "linkMode": "imported_file",
                    "filename": "paper.pdf",
                },
            }
        ]
    return item


def test_audit_collection_full_compliance(auditor, mock_gateway, children_data):
    mock_gateway.get_collection_id_by_name.return_value = "COL_ID"
    mock_gateway.get_item_children.side_effect = lambda k: children_data.get(k, [])

    item1 = create_mock_item(children_data, "ITEM1", "Title 1", "Abstract 1", "10.1/1", None, True)
    item2 = create_mock_item(
        children_data, "ITEM2", "Title 2", "Abstract 2", None, "2301.00001", True
    )
    mock_gateway.get_items_in_collection.return_value = iter([item1, item2])

    report = auditor.audit_collection("Test Collection")

    assert report is not None
    assert report.total_items == 2
    assert len(report.items_missing_id) == 0
    assert len(report.items_missing_title) == 0
    assert len(report.items_missing_abstract) == 0
    assert len(report.items_missing_pdf) == 0


def test_audit_collection_missing_attributes(auditor, mock_gateway, children_data):
    mock_gateway.get_collection_id_by_name.return_value = "COL_ID"
    mock_gateway.get_item_children.side_effect = lambda k: children_data.get(k, [])

    item1 = create_mock_item(children_data, "ITEM1", None, "Abstract 1", "10.1/1", None, False)
    item2 = create_mock_item(children_data, "ITEM2", "Title 2", None, None, None, True)
    item3 = create_mock_item(children_data, "ITEM3", "Title 3", "Abstract 3", None, None, False)
    mock_gateway.get_items_in_collection.return_value = iter([item1, item2, item3])

    report = auditor.audit_collection("Test Collection")

    assert report is not None
    assert report.total_items == 3
    assert len(report.items_missing_id) == 2
    assert item2 in report.items_missing_id
    assert item3 in report.items_missing_id
    assert len(report.items_missing_title) == 1
    assert item1 in report.items_missing_title
    assert len(report.items_missing_abstract) == 1
    assert item2 in report.items_missing_abstract
    assert len(report.items_missing_pdf) == 2
    assert item1 in report.items_missing_pdf
    assert item3 in report.items_missing_pdf


def test_audit_collection_not_found(auditor, mock_gateway):
    mock_gateway.get_collection_id_by_name.return_value = None

    mock_gateway.get_collection.return_value = None

    report = auditor.audit_collection("Non Existent Collection")

    assert report is None


# --- CSV Enrichment Tests ---


def test_enrich_from_csv_success(auditor, mock_gateway, tmp_path):
    csv_file = tmp_path / "decisions.csv"
    csv_file.write_text(
        "title,status,reason,comment\n"
        "Paper A,Included,EC1,Looks good\n"
        "Paper B,Excluded,EC2,Out of scope\n"
    )

    # Mock items in library
    item1 = create_mock_item({}, "KEY1", title="Paper A")
    item2 = create_mock_item({}, "KEY2", title="Paper B")

    mock_gateway.search_items.return_value = iter([item1, item2])
    mock_gateway.get_item_children.return_value = []
    mock_gateway.create_note.return_value = True

    results = auditor.enrich_from_csv(str(csv_file), reviewer="Orion", dry_run=False, force=True)

    assert results["matched"] == 2
    assert results["created"] == 2
    assert mock_gateway.create_note.call_count == 2


def test_enrich_from_csv_match_by_doi(auditor, mock_gateway, tmp_path):
    csv_file = tmp_path / "decisions.csv"
    csv_file.write_text("doi,status,reason,comment\n10.1234/5678,Included,EC1,Matches DOI\n")

    # Item has DOI but different title
    item1 = create_mock_item({}, "KEY1", title="Random Title", doi="10.1234/5678")

    mock_gateway.search_items.return_value = iter([item1])
    mock_gateway.get_item_children.return_value = []
    mock_gateway.create_note.return_value = True

    results = auditor.enrich_from_csv(str(csv_file), reviewer="Orion", dry_run=False, force=True)

    assert results["matched"] == 1
    assert results["created"] == 1


def test_enrich_from_csv_update_existing(auditor, mock_gateway, tmp_path):
    csv_file = tmp_path / "decisions.csv"
    csv_file.write_text("key,status,reason,comment\nKEY1,Included,EC1,Update\n")

    item1 = create_mock_item({}, "KEY1", title="Paper A")

    mock_gateway.search_items.return_value = iter([item1])
    # Mock existing SDB note for Orion
    mock_gateway.get_item_children.return_value = [
        {
            "key": "NOTE1",
            "version": 1,
            "data": {"itemType": "note", "note": '{"audit_version": "1.1", "persona": "Orion"}'},
        }
    ]
    mock_gateway.update_note.return_value = True

    results = auditor.enrich_from_csv(str(csv_file), reviewer="Orion", dry_run=False, force=True)

    assert results["matched"] == 1
    assert results["updated"] == 1
    mock_gateway.update_note.assert_called_once()
