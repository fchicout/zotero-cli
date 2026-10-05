"""Issue #541: exports say when they add SDB notes to references, once."""

from unittest.mock import create_autospec

from zotero_cli.core.interfaces import BibtexGateway, RisGateway
from zotero_cli.core.services.export_service import ExportService
from zotero_cli.core.services.sdb.sdb_service import SDBService
from zotero_cli.core.zotero_item import ZoteroItem


def _item(key: str) -> ZoteroItem:
    return ZoteroItem(key=key, version=1, item_type="journalArticle", title=key, raw_data={})


def _service(entries: dict, messages: list) -> ExportService:
    sdb = create_autospec(SDBService, instance=True)
    sdb.inspect_items_sdb.return_value = entries
    service = ExportService(
        create_autospec(object, instance=True),
        create_autospec(BibtexGateway, instance=True),
        create_autospec(RisGateway, instance=True),
        sdb,
    )
    service.notify = messages.append
    return service


def test_the_notice_is_said_once_when_sdb_notes_are_added():
    messages: list = []
    service = _service({"A": [{"decision": "accepted"}], "B": []}, messages)

    service._map_items_to_papers([_item("A"), _item("B")])
    service._map_items_to_papers([_item("A")])

    assert len(messages) == 1
    assert "deprecated and stops in 4.0.0" in messages[0]


def test_no_notice_without_sdb_notes():
    messages: list = []
    service = _service({"A": [], "B": []}, messages)

    service._map_items_to_papers([_item("A"), _item("B")])

    assert messages == []
