from unittest.mock import Mock

import pytest

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.slr.csv_inbound import CSVInboundService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return Mock(spec=ZoteroGateway)


@pytest.fixture
def service(mock_gateway):
    return CSVInboundService(mock_gateway)


def create_mock_item(key, title=None, abstract=None, doi=None, arxiv_id=None):
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
    return ZoteroItem.from_raw_zotero_item(raw_item)


def test_enrich_from_csv_success(service, mock_gateway, tmp_path):
    csv_file = tmp_path / "decisions.csv"
    csv_file.write_text(
        "title,status,reason,comment\n"
        "Paper A,Included,EC1,Looks good\n"
        "Paper B,Excluded,EC2,Out of scope\n"
    )

    item1 = create_mock_item("KEY1", title="Paper A")
    item2 = create_mock_item("KEY2", title="Paper B")

    mock_gateway.search_items.return_value = iter([item1, item2])
    mock_gateway.get_item_children.return_value = []
    mock_gateway.create_note.return_value = True

    results = service.enrich_from_csv(str(csv_file), reviewer="Orion", dry_run=False, force=True)

    assert results["matched"] == 2
    assert results["created"] == 2
    assert mock_gateway.create_note.call_count == 2


def test_enrich_from_csv_match_by_doi(service, mock_gateway, tmp_path):
    csv_file = tmp_path / "decisions.csv"
    csv_file.write_text("doi,status,reason,comment\n10.1234/5678,Included,EC1,Matches DOI\n")

    item1 = create_mock_item("KEY1", title="Random Title", doi="10.1234/5678")

    mock_gateway.search_items.return_value = iter([item1])
    mock_gateway.get_item_children.return_value = []
    mock_gateway.create_note.return_value = True

    results = service.enrich_from_csv(str(csv_file), reviewer="Orion", dry_run=False, force=True)

    assert results["matched"] == 1
    assert results["created"] == 1


def test_enrich_from_csv_update_existing(service, mock_gateway, tmp_path):
    csv_file = tmp_path / "decisions.csv"
    csv_file.write_text("key,status,reason,comment\nKEY1,Included,EC1,Update\n")

    item1 = create_mock_item("KEY1", title="Paper A")

    mock_gateway.search_items.return_value = iter([item1])
    mock_gateway.get_item_children.return_value = [
        {
            "key": "NOTE1",
            "version": 1,
            "data": {
                "itemType": "note",
                "note": '{"audit_version": "1.2", "persona": "Orion", "phase": "title_abstract"}',
            },
        }
    ]

    mock_gateway.update_note.return_value = True

    results = service.enrich_from_csv(str(csv_file), reviewer="Orion", dry_run=False, force=True)

    assert results["matched"] == 1
    assert results["updated"] == 1
    mock_gateway.update_note.assert_called_once()


def test_enrich_from_csv_with_evidence(service, mock_gateway, tmp_path):
    csv_file = tmp_path / "decisions_with_evidence.csv"
    csv_file.write_text("key,status,reason,evidence\nKEY1,Included,EC1,Found evidence on page 10\n")

    item1 = create_mock_item("KEY1", title="Paper A")
    mock_gateway.search_items.return_value = iter([item1])
    mock_gateway.get_item_children.return_value = []
    mock_gateway.create_note.return_value = True

    results = service.enrich_from_csv(str(csv_file), reviewer="Orion", dry_run=False, force=True)

    assert results["matched"] == 1
    assert results["created"] == 1

    args, _ = mock_gateway.create_note.call_args
    note_content = args[1]
    assert "Found evidence on page 10" in note_content
    assert '"evidence":' in note_content


def test_enrich_from_csv_with_move(service, mock_gateway, tmp_path):
    csv_file = tmp_path / "move_decisions.csv"
    csv_file.write_text("key,status\nKEY_INC,Included\nKEY_EXC,Excluded\n")

    item_inc = create_mock_item("KEY_INC", title="Accepted Paper")
    item_exc = create_mock_item("KEY_EXC", title="Rejected Paper")

    mock_gateway.search_items.return_value = iter([item_inc, item_exc])
    mock_gateway.get_item_children.return_value = []
    mock_gateway.create_note.return_value = True

    mock_col_service = Mock()

    results = service.enrich_from_csv(
        str(csv_file),
        reviewer="Orion",
        dry_run=False,
        force=True,
        move_to_included="Included_Col",
        move_to_excluded="Excluded_Col",
        collection_service=mock_col_service,
    )

    assert results["matched"] == 2
    assert results["created"] == 2

    assert mock_col_service.move_item.call_count == 2
    mock_col_service.move_item.assert_any_call(
        source_col_name=None, dest_col_name="Included_Col", identifier="KEY_INC"
    )
    mock_col_service.move_item.assert_any_call(
        source_col_name=None, dest_col_name="Excluded_Col", identifier="KEY_EXC"
    )


def test_enrich_from_csv_no_move_without_flags(service, mock_gateway, tmp_path):
    csv_file = tmp_path / "no_move.csv"
    csv_file.write_text("key,status\nKEY1,Included\n")

    item1 = create_mock_item("KEY1", title="Paper A")
    mock_gateway.search_items.return_value = iter([item1])
    mock_gateway.get_item_children.return_value = []
    mock_gateway.create_note.return_value = True

    mock_col_service = Mock()

    service.enrich_from_csv(
        str(csv_file),
        reviewer="Orion",
        dry_run=False,
        force=True,
        collection_service=mock_col_service,
    )
    assert mock_col_service.move_item.call_count == 0

    service.enrich_from_csv(
        str(csv_file),
        reviewer="Orion",
        dry_run=True,
        force=True,
        move_to_included="Included_Col",
        collection_service=mock_col_service,
    )
    assert mock_col_service.move_item.call_count == 0


def test_enrich_from_csv_missing_columns(service, tmp_path):
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text("wrong_col,status\nKEY1,Included\n")

    results = service.enrich_from_csv(str(csv_file), reviewer="O", column_map={"key": "Key"})
    assert "error" in results
    assert "Missing columns" in results["error"]


def test_enrich_from_csv_file_not_found(service):
    results = service.enrich_from_csv("non_existent.csv", reviewer="O")
    assert "error" in results
