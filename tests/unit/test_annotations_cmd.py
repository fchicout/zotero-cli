"""`item annotations`, the Web API reader and `item export --annotations` (Issue #558)."""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, create_autospec, patch

import pytest
import requests

from zotero_cli.cli.commands.item_cmd import ItemCommand
from zotero_cli.cli.main import build_parser
from zotero_cli.core import annotations as ann
from zotero_cli.core.exceptions import NotFound, UsageError
from zotero_cli.core.interfaces import (
    CollectionRepository,
    ItemRepository,
    NoteRepository,
    ZoteroGateway,
)
from zotero_cli.core.services.attachment_service import AttachmentService
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.repositories import ZoteroAttachmentRepository
from zotero_cli.infra.zotero_api import ZoteroAPIClient

# ---- the Web API reader -------------------------------------------------------------------


class RoutedSession:
    """Answers each request from a table keyed by the end of the URL."""

    def __init__(self, routes: Dict[str, Any]):
        self.routes = routes
        self.headers: Dict[str, str] = {}
        self.requested: List[str] = []

    def get(self, url: str, params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> MagicMock:
        suffix = next(
            (s for s in sorted(self.routes, key=len, reverse=True) if url.endswith("/" + s)), None
        )
        assert suffix is not None, f"unexpected request {url}"
        self.requested.append(suffix)
        payload = self.routes[suffix]
        response = MagicMock(spec=requests.Response)
        response.json.return_value = payload
        response.headers = {"Total-Results": str(len(payload))} if isinstance(payload, list) else {}
        response.raise_for_status.return_value = None
        return response


def _client(routes: Dict[str, Any]) -> tuple:
    session = RoutedSession(routes)
    client = ZoteroAPIClient("key", "123", "user")
    client.http.session = session  # type: ignore[assignment]
    return client, session


def _item(key: str, item_type: str = "journalArticle") -> Dict[str, Any]:
    return {"key": key, "data": {"key": key, "version": 1, "itemType": item_type, "title": key}}


def _annotation(key: str, parent: str, sort_index: str, **data: Any) -> Dict[str, Any]:
    return {
        "key": key,
        "data": {
            "itemType": "annotation",
            "parentItem": parent,
            "annotationType": "highlight",
            "annotationSortIndex": sort_index,
            **data,
        },
    }


def test_the_annotations_of_every_pdf_attachment_of_an_item() -> None:
    client, session = _client(
        {
            "items/ITEM1": _item("ITEM1"),
            "items/ITEM1/children": [
                _item("PDF1", "attachment"),
                {"key": "NOTE1", "data": {"itemType": "note"}},
                _item("PDF2", "attachment"),
            ],
            "items/PDF1/children": [
                _annotation("A2", "PDF1", "00002", annotationText="second"),
                _annotation("A1", "PDF1", "00001", annotationText="first", annotationPageLabel="4"),
                {"key": "X", "data": {"itemType": "note"}},
            ],
            "items/PDF2/children": [_annotation("B1", "PDF2", "00001", annotationText="other pdf")],
        }
    )

    found = client.get_annotations("ITEM1")

    assert [a["key"] for a in found] == ["A1", "A2", "B1"]
    assert (found[0]["text"], found[0]["page"], found[0]["attachment"]) == ("first", "4", "PDF1")
    assert "items/NOTE1/children" not in session.requested  # only attachments are searched


def test_an_attachment_key_reads_its_own_annotations() -> None:
    client, session = _client(
        {
            "items/PDF1": _item("PDF1", "attachment"),
            "items/PDF1/children": [_annotation("A1", "PDF1", "00001")],
        }
    )

    assert [a["key"] for a in client.get_annotations("PDF1")] == ["A1"]
    assert session.requested == ["items/PDF1", "items/PDF1/children"]


def test_an_item_without_attachments_asks_for_no_annotations() -> None:
    client, session = _client({"items/ITEM1": _item("ITEM1"), "items/ITEM1/children": []})

    assert client.get_annotations("ITEM1") == []
    assert session.requested == ["items/ITEM1", "items/ITEM1/children"]


# ---- the adapter ----------------------------------------------------------------------------


def test_the_attachment_repository_delegates_to_the_gateway() -> None:
    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.get_annotations.return_value = [ann.build("A1", "P", "note")]

    assert ZoteroAttachmentRepository(gateway).get_annotations("ITEM1")[0]["key"] == "A1"
    gateway.get_annotations.assert_called_once_with("ITEM1")


# ---- the command ----------------------------------------------------------------------------

SAMPLE = [
    ann.build(
        "A1", "PDF1", "highlight", "the claim", "check", "#ffd400", "12", ["x"], "2026-02-01"
    ),
    ann.build("A2", "PDF1", "note", "", "loose thought", "#ff6666", "3", [], "2026-02-02"),
    ann.build(
        "A3", "PDF1", "underline", "underlined", "", "#2ea8e5", "5", ["y", "z"], "2026-02-03"
    ),
]


def _run(
    capsys: pytest.CaptureFixture[str],
    *argv: str,
    annotations: Optional[List[Dict[str, Any]]] = None,
    found: bool = True,
) -> str:
    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.get_item.return_value = (
        ZoteroItem(key="ITEM1", version=1, item_type="journalArticle", title="T") if found else None
    )
    gateway.get_annotations.return_value = SAMPLE if annotations is None else annotations
    args = build_parser().parse_args(["item", "annotations", *argv])
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=gateway):
        ItemCommand().execute(args)
    return capsys.readouterr().out


def test_the_options_parse() -> None:
    args = build_parser().parse_args(
        [
            "item",
            "annotations",
            "ITEM1",
            "--type",
            "highlight",
            "--type",
            "note",
            "--format",
            "json",
        ]
    )
    assert (args.key, args.annotation_type, args.format) == ("ITEM1", ["highlight", "note"], "json")
    assert build_parser().parse_args(["item", "annotations", "--key", "ITEM1"]).key_flag == "ITEM1"


def test_an_unknown_annotation_type_is_refused() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as exit_info:
        parser.parse_args(["item", "annotations", "ITEM1", "--type", "doodle"])
    assert exit_info.value.code == 2


def test_the_table_shows_page_type_text_comment_and_tags(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = _run(capsys, "ITEM1")
    for expected in ("Annotations (3)", "the claim", "check", "loose thought", "underlined"):
        assert expected in out


def test_json_carries_every_field(capsys: pytest.CaptureFixture[str]) -> None:
    rows = json.loads(_run(capsys, "--key", "ITEM1", "--format", "json"))
    assert [r["key"] for r in rows] == ["A1", "A2", "A3"]
    assert set(rows[0]) == {
        "page", "type", "text", "comment", "tags", "key", "attachment", "color", "date_added",
    }  # fmt: skip
    assert rows[0]["tags"] == ["x"]


def test_only_the_requested_types_are_kept(capsys: pytest.CaptureFixture[str]) -> None:
    rows = json.loads(
        _run(capsys, "ITEM1", "--type", "highlight", "--type", "underline", "--format", "json")
    )
    assert [r["key"] for r in rows] == ["A1", "A3"]


def test_ndjson_and_keys(capsys: pytest.CaptureFixture[str]) -> None:
    lines = _run(capsys, "ITEM1", "--format", "ndjson").splitlines()
    assert [json.loads(line)["key"] for line in lines] == ["A1", "A2", "A3"]
    assert _run(capsys, "ITEM1", "--format", "keys") == "A1\nA2\nA3\n"


def test_csv_has_one_row_per_annotation(capsys: pytest.CaptureFixture[str]) -> None:
    out = _run(capsys, "ITEM1", "--format", "csv").splitlines()
    assert len(out) == 4  # header and three rows
    assert out[0].startswith("page,type,text")


def test_no_annotations_is_a_message_in_the_table_and_an_empty_list_as_data(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert "No annotations found" in _run(capsys, "ITEM1", annotations=[])
    assert json.loads(_run(capsys, "ITEM1", "--format", "json", annotations=[])) == []
    assert _run(capsys, "ITEM1", "--format", "keys", annotations=[]) == ""


def test_an_unknown_item_is_not_found(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(NotFound, match="Item 'ITEM1' not found"):
        _run(capsys, "ITEM1", found=False)


def test_a_key_is_required(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(UsageError, match="item key is required"):
        _run(capsys)


def test_two_different_keys_are_refused(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(UsageError, match="Two different item keys"):
        _run(capsys, "ITEM1", "--key", "OTHER")


# ---- item export --as md --annotations --------------------------------------------------------


def _attachments(mock_attachment_repo: Any) -> AttachmentService:
    return AttachmentService(
        create_autospec(ItemRepository, instance=True),
        create_autospec(CollectionRepository, instance=True),
        mock_attachment_repo,
        create_autospec(NoteRepository, instance=True),
        create_autospec(MetadataAggregatorService, instance=True),
    )


def _export(service: AttachmentService, tmp_path: Path, include: bool) -> str:
    setattr(service, "get_fulltext", MagicMock(return_value="BODY TEXT\n"))
    item = ZoteroItem(key="ITEM1", version=1, item_type="journalArticle", title="A Paper")
    assert service._export_item_markdown(item, tmp_path, "PDF1", include) == "success"
    return next(tmp_path.glob("ITEM1_*.md")).read_text(encoding="utf-8")


def test_the_markdown_ends_with_the_annotations_when_asked(
    mock_attachment_repo: Any, tmp_path: Path
) -> None:
    mock_attachment_repo.get_annotations.return_value = SAMPLE[:1]

    text = _export(_attachments(mock_attachment_repo), tmp_path, True)

    assert text.startswith("BODY TEXT\n\n## Annotations\n")
    assert '- **p. 12, highlight:** "the claim"' in text
    assert "  - Comment: check" in text
    mock_attachment_repo.get_annotations.assert_called_once_with("ITEM1")


def test_the_markdown_is_unchanged_without_the_option(
    mock_attachment_repo: Any, tmp_path: Path
) -> None:
    text = _export(_attachments(mock_attachment_repo), tmp_path, False)

    assert text == "BODY TEXT\n"
    mock_attachment_repo.get_annotations.assert_not_called()


def test_an_item_with_no_annotations_gets_no_empty_section(
    mock_attachment_repo: Any, tmp_path: Path
) -> None:
    mock_attachment_repo.get_annotations.return_value = []
    assert _export(_attachments(mock_attachment_repo), tmp_path, True) == "BODY TEXT\n"


def test_unreadable_annotations_do_not_fail_the_export(
    mock_attachment_repo: Any, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    mock_attachment_repo.get_annotations.side_effect = RuntimeError("boom")

    assert _export(_attachments(mock_attachment_repo), tmp_path, True) == "BODY TEXT\n"
    assert "could not read the annotations of ITEM1: boom" in caplog.text


def _export_args(**extra: Any) -> argparse.Namespace:
    base = dict(
        verb="export", key="ITEM1", export_format="md", output=None, user=False,
        style="apa", render="plain", annotations=True,
    )  # fmt: skip
    return argparse.Namespace(**{**base, **extra})


def test_the_export_flag_reaches_the_service(tmp_path: Path) -> None:
    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.get_item.return_value = ZoteroItem(key="ITEM1", version=1, item_type="book", title="T")
    service = create_autospec(AttachmentService, instance=True)
    service.bulk_export_markdown.return_value = {"success": 1, "skipped": 0, "failed": 0}

    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=gateway),
        patch(
            "zotero_cli.infra.factory.GatewayFactory.get_attachment_service", return_value=service
        ),
    ):
        ItemCommand().execute(_export_args(output=str(tmp_path)))

    assert service.bulk_export_markdown.call_args.kwargs["include_annotations"] is True


def test_annotations_only_apply_to_markdown_export() -> None:
    gateway = create_autospec(ZoteroGateway, instance=True)
    gateway.get_item.return_value = ZoteroItem(key="ITEM1", version=1, item_type="book", title="T")
    command = ItemCommand()
    args = _export_args(export_format="bibtex", output="x.bib")

    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=gateway):
        with pytest.raises(UsageError, match="only applies to --as md"):
            command.execute(args)
