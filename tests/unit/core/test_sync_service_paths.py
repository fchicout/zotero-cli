"""SyncService.recover_state_from_notes: the paths around the happy one (Issue #389).

Uses the shared autospec repositories from tests/unit/conftest.py.
"""

import csv
import json
from pathlib import Path
from typing import Any, List, Optional
from unittest.mock import patch

import pytest

from zotero_cli.core.services.sync_service import SyncService
from zotero_cli.core.zotero_item import ZoteroItem


def _item(key: str = "K1", title: Optional[str] = "Paper") -> ZoteroItem:
    return ZoteroItem(key=key, version=1, item_type="journalArticle", title=title)


def _note(payload: dict[str, Any]) -> dict[str, Any]:
    return {"data": {"itemType": "note", "note": f"<p>{json.dumps(payload)}</p>"}}


SDB = {"audit_version": "1.2", "decision": "accepted", "reason_code": ["IC1"], "reason_text": "ok"}


@pytest.fixture
def said() -> List[str]:
    return []


@pytest.fixture
def service(mock_collection_repo: Any, mock_item_repo: Any, said: List[str]) -> SyncService:
    mock_collection_repo.get_collection_id_by_name.return_value = "COL"
    service = SyncService(mock_collection_repo, mock_item_repo)
    service.notify = said.append
    return service


def _rows(path: Path) -> List[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_progress_is_reported_for_each_stage(
    service: SyncService, mock_collection_repo: Any, mock_item_repo: Any, tmp_path: Path
) -> None:
    mock_collection_repo.get_items_in_collection.return_value = [_item()]
    mock_item_repo.get_item_children.return_value = [_note(SDB)]
    steps: List[str] = []

    service.recover_state_from_notes(
        "Col", str(tmp_path / "o.csv"), lambda current, total, message: steps.append(message)
    )

    assert steps[0] == "Resolving collection ID..."
    assert steps[1] == "Fetching items from 'Col'..."
    assert steps[2].startswith("Scanning: Paper")


def test_a_failed_batched_lookup_falls_back_to_one_request_per_item(
    service: SyncService, mock_collection_repo: Any, mock_item_repo: Any, tmp_path: Path
) -> None:
    mock_collection_repo.get_items_in_collection.return_value = [_item()]
    mock_item_repo.get_item_children.return_value = [_note(SDB)]
    out = tmp_path / "o.csv"

    with patch(
        "zotero_cli.core.services.sync_service.children_by_parent",
        side_effect=RuntimeError("search failed"),
    ):
        assert service.recover_state_from_notes("Col", str(out)) is True

    assert [row["key"] for row in _rows(out)] == ["K1"]
    mock_item_repo.get_item_children.assert_called_once_with("K1")


def test_legacy_note_fields_are_mapped_to_the_csv_columns(
    service: SyncService, mock_collection_repo: Any, mock_item_repo: Any, tmp_path: Path
) -> None:
    legacy = {
        "audit_version": "1.0",
        "decision": "rejected",
        "criteria": ["EC1", "EC2"],
        "reason": "off topic",
    }
    mock_collection_repo.get_items_in_collection.return_value = [_item()]
    mock_item_repo.get_item_children.return_value = [_note(legacy)]
    out = tmp_path / "o.csv"

    service.recover_state_from_notes("Col", str(out))

    [row] = _rows(out)
    assert (row["decision"], row["criteria"], row["reason"]) == ("rejected", "EC1,EC2", "off topic")


def test_a_scalar_criteria_value_is_written_as_text(
    service: SyncService, mock_collection_repo: Any, mock_item_repo: Any, tmp_path: Path
) -> None:
    scalar = {"audit_version": "1.0", "decision": "accepted", "criteria": "IC9"}
    mock_collection_repo.get_items_in_collection.return_value = [_item(title=None)]
    mock_item_repo.get_item_children.return_value = [_note(scalar)]
    out = tmp_path / "o.csv"

    service.recover_state_from_notes("Col", str(out))

    [row] = _rows(out)
    assert (row["title"], row["criteria"]) == ("No Title", "IC9")


def test_one_bad_item_does_not_stop_the_others(
    service: SyncService,
    mock_collection_repo: Any,
    mock_item_repo: Any,
    said: List[str],
    tmp_path: Path,
) -> None:
    mock_collection_repo.get_items_in_collection.return_value = [_item("BAD"), _item("OK")]
    mock_item_repo.get_item_children.return_value = [_note(SDB)]
    original = service._extract_screening_data

    def flaky(item: ZoteroItem, children: Any = None) -> Any:
        if item.key == "BAD":
            raise RuntimeError("boom")
        return original(item, children)

    out = tmp_path / "o.csv"
    with patch.object(service, "_extract_screening_data", side_effect=flaky):
        assert service.recover_state_from_notes("Col", str(out)) is True

    assert [row["key"] for row in _rows(out)] == ["OK"]
    assert any("Failed on item BAD: boom" in message for message in said)


def test_no_screening_notes_means_no_file(
    service: SyncService,
    mock_collection_repo: Any,
    mock_item_repo: Any,
    said: List[str],
    tmp_path: Path,
) -> None:
    mock_collection_repo.get_items_in_collection.return_value = [_item()]
    mock_item_repo.get_item_children.return_value = []
    out = tmp_path / "o.csv"

    assert service.recover_state_from_notes("Col", str(out)) is True

    assert not out.exists()
    assert any("No screening notes found in 'Col'" in message for message in said)


def test_an_unwritable_destination_is_reported(
    service: SyncService,
    mock_collection_repo: Any,
    mock_item_repo: Any,
    said: List[str],
    tmp_path: Path,
) -> None:
    mock_collection_repo.get_items_in_collection.return_value = [_item()]
    mock_item_repo.get_item_children.return_value = [_note(SDB)]

    assert service.recover_state_from_notes("Col", str(tmp_path)) is False  # a directory

    assert any(message.startswith("Error writing CSV file") for message in said)


def test_children_that_cannot_be_fetched_skip_the_item(
    service: SyncService,
    mock_collection_repo: Any,
    mock_item_repo: Any,
    said: List[str],
    tmp_path: Path,
) -> None:
    mock_collection_repo.get_items_in_collection.return_value = [_item()]
    mock_item_repo.get_item_children.side_effect = RuntimeError("offline")

    with patch(
        "zotero_cli.core.services.sync_service.children_by_parent", side_effect=RuntimeError("x")
    ):
        assert service.recover_state_from_notes("Col", str(tmp_path / "o.csv")) is True

    assert any("Failed to fetch children for K1: offline" in message for message in said)


@pytest.mark.parametrize(
    "note_html",
    [
        "<p>{not json}</p>",
        '<p>{"decision": "accepted"}</p>',  # JSON, but not an SDB note
        "plain text without braces",
    ],
)
def test_notes_that_are_not_sdb_decisions_are_ignored(service: SyncService, note_html: str) -> None:
    child = {"data": {"itemType": "note", "note": note_html}}
    assert service._extract_screening_data(_item(), [child]) is None


def test_non_note_children_are_ignored(service: SyncService) -> None:
    attachment = {"data": {"itemType": "attachment"}}
    assert service._extract_screening_data(_item(), [attachment]) is None
