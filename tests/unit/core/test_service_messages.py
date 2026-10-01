"""What ExportService, CollectionService and ScreeningService tell their caller (Issue #393).

They report through `notify` (or the logger), never print: each message is
captured here by passing a sink, and nothing may reach stdout/stderr.
"""

import logging
from typing import List
from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.collection_service import CollectionService
from zotero_cli.core.services.export_service import ExportService
from zotero_cli.core.services.screening_service import ScreeningService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def said() -> List[str]:
    return []


def _item(key="K1", collections=None, doi=None):
    return ZoteroItem(
        key=key,
        version=1,
        item_type="journalArticle",
        title="T",
        doi=doi,
        collections=collections or [],
    )


def _silent(capsys):
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


# ---- ExportService --------------------------------------------------------------


def _export(said):
    service = ExportService(MagicMock(), MagicMock(), MagicMock(), MagicMock())
    service.notify = said.append
    return service


def test_export_missing_collection(said, capsys):
    service = _export(said)
    service.collection_repo.get_collection_id_by_name.return_value = None
    assert service.export_collection("Nope", "o.bib") is False
    assert said == ["Error: Collection 'Nope' not found."]
    _silent(capsys)


def test_export_empty_collection(said, capsys):
    service = _export(said)
    service.collection_repo.get_collection_id_by_name.return_value = "C"
    service.collection_repo.get_items_in_collection.return_value = iter([])
    assert service.export_collection("Empty", "o.bib") is False
    assert said == ["Warning: Collection 'Empty' is empty."]
    _silent(capsys)


def test_export_without_valid_papers(said, capsys):
    service = _export(said)
    service.sdb_service.inspect_items_sdb.return_value = {}
    attachment = ZoteroItem(key="A", version=1, item_type="attachment", title="a")
    assert service.export_items([attachment], "o.bib") is False
    assert said == ["Warning: No valid papers to export."]
    _silent(capsys)


def test_export_unsupported_format(said, capsys):
    service = _export(said)
    service.sdb_service.inspect_items_sdb.return_value = {}
    assert service.export_items([_item()], "o.x", "docx") is False
    assert said == ["Error: Unsupported export format 'docx'."]
    _silent(capsys)


# ---- CollectionService ---------------------------------------------------------


def _collections(said):
    collection_repo = MagicMock()
    collection_repo.get_collection_id_by_name.side_effect = lambda name: name
    service = CollectionService(MagicMock(), collection_repo)
    service.notify = said.append
    return service


def test_move_item_not_found_anywhere(said, capsys):
    service = _collections(said)
    service.item_repo.get_item.return_value = None
    assert service.move_item(None, "Dest", "MISSING") is False
    assert said == ["Item 'MISSING' not found."]
    _silent(capsys)


def test_move_item_lookup_by_identifier_announces_the_slow_search(said, capsys):
    service = _collections(said)
    service.item_repo.get_item.return_value = None
    service.collection_repo.get_items_in_collection.return_value = iter([])
    assert service.move_item("Src", "Dest", "10.1/x") is False
    assert said[0].startswith("Item key '10.1/x' lookup failed. Searching by DOI/ArXiv in 'Src'")
    assert said[1] == "Item '10.1/x' not found."
    _silent(capsys)


def test_move_item_with_an_ambiguous_source(said, capsys):
    service = _collections(said)
    service.item_repo.get_item.return_value = _item(collections=["A", "B"])
    assert service.move_item(None, "Dest", "K1") is False
    assert len(said) == 1
    assert said[0].startswith("Error: Ambiguous source. Item 'K1' is in multiple collections")
    _silent(capsys)


def test_move_item_from_root_when_it_is_in_a_collection(said, capsys):
    service = _collections(said)
    service.item_repo.get_item.return_value = _item(collections=["A"])
    assert service.move_item("root", "Dest", "K1") is False
    assert said == ["Item 'K1' found but it is NOT in the root folder."]
    _silent(capsys)


def test_move_item_not_in_the_named_source(said, capsys):
    service = _collections(said)
    service.item_repo.get_item.return_value = _item(collections=["A"])
    assert service.move_item("Other", "Dest", "K1") is False
    assert said == ["Item 'K1' found but not in source collection 'Other'."]
    _silent(capsys)


# ---- ScreeningService ------------------------------------------------------------


def _screening(said):
    note_repo = MagicMock()
    note_repo.get_item_children.return_value = []
    service = ScreeningService(MagicMock(), MagicMock(), note_repo, MagicMock(), MagicMock())
    service.notify = said.append
    return service


def test_record_note_rejects_an_invalid_decision(said, capsys):
    service = _screening(said)
    assert service.record_decision_note("K1", "MAYBE", "") is False
    assert said == ["Error: Invalid decision 'MAYBE'. Must be INCLUDE or EXCLUDE."]
    _silent(capsys)


def test_record_note_reports_a_failed_write(said, capsys):
    service = _screening(said)
    service.note_repo.create_note.return_value = False
    assert service.record_decision_note("K1", "INCLUDE", "") is False
    assert said == ["Error: Failed to record audit note for item K1."]
    _silent(capsys)


def test_apply_outcome_rejects_an_invalid_decision(said, capsys):
    service = _screening(said)
    assert service.apply_decision_outcome("K1", "MAYBE", "") is False
    assert said == ["Error: Invalid decision 'MAYBE'. Must be INCLUDE or EXCLUDE."]
    _silent(capsys)


def test_apply_outcome_warns_when_tags_or_the_move_fail(said, capsys):
    service = _screening(said)
    service.tag_repo.add_tags.return_value = False
    service.collection_service.move_item.return_value = False
    assert service.apply_decision_outcome("K1", "INCLUDE", "", "Src", "Dest") is True
    assert said[0].startswith("Warning: Failed to apply tags")
    assert said[1] == "Warning: Decision recorded but failed to move item K1."
    _silent(capsys)


def test_without_a_sink_the_same_messages_are_logged_at_their_level(caplog, capsys):
    service = ScreeningService(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
    with caplog.at_level(logging.DEBUG):
        service.record_decision_note("K1", "MAYBE", "")
    assert [r.levelno for r in caplog.records] == [logging.ERROR]
    _silent(capsys)
