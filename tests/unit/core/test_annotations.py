"""PDF annotation records and their Markdown form (Issue #558)."""

from typing import Any, Dict

from zotero_cli.core import annotations as ann


def test_build_fills_every_field_with_defaults() -> None:
    record = ann.build("A1", "ATT", "highlight")
    assert record == {
        "key": "A1",
        "attachment": "ATT",
        "type": "highlight",
        "text": "",
        "comment": "",
        "color": "",
        "page": "",
        "tags": [],
        "date_added": "",
        "sort_index": "",
    }


def test_the_sqlite_type_codes_are_zoteros() -> None:
    assert ann.SQLITE_TYPES == {
        1: "highlight",
        2: "note",
        3: "image",
        4: "ink",
        5: "underline",
        6: "text",
    }
    assert ann.TYPES == ("highlight", "note", "image", "ink", "underline", "text")


def _raw(**data: Any) -> Dict[str, Any]:
    base = {"itemType": "annotation", "parentItem": "ATT1", "annotationType": "highlight"}
    return {"key": "AN1", "data": {**base, **data}}


def test_an_api_annotation_item_becomes_a_record() -> None:
    record = ann.from_api(
        _raw(
            annotationText="marked",
            annotationComment="so what",
            annotationColor="#ffd400",
            annotationPageLabel="12",
            annotationSortIndex="00011|000200|00040",
            tags=[{"tag": "important"}, {"tag": ""}],
            dateAdded="2026-02-03T04:05:06Z",
        )
    )
    assert record == {
        "key": "AN1",
        "attachment": "ATT1",
        "type": "highlight",
        "text": "marked",
        "comment": "so what",
        "color": "#ffd400",
        "page": "12",
        "tags": ["important"],
        "date_added": "2026-02-03T04:05:06Z",
        "sort_index": "00011|000200|00040",
    }


def test_something_that_is_not_an_annotation_is_ignored() -> None:
    assert ann.from_api({"key": "N1", "data": {"itemType": "note"}}) is None
    assert ann.from_api({"key": "X", "data": {}}) is None


def test_missing_api_fields_become_empty_strings() -> None:
    record = ann.from_api({"key": "AN2", "data": {"itemType": "annotation"}})
    assert record is not None
    assert (record["type"], record["text"], record["page"], record["tags"]) == ("", "", "", [])


def test_reading_order_is_by_attachment_then_sort_index() -> None:
    a = ann.build("A", "P2", "note", sort_index="00001")
    b = ann.build("B", "P1", "note", sort_index="00009")
    c = ann.build("C", "P1", "note", sort_index="00002")
    assert [r["key"] for r in ann.in_reading_order([a, b, c])] == ["C", "B", "A"]


def test_markdown_is_empty_without_annotations() -> None:
    assert ann.to_markdown([]) == ""


def test_markdown_lists_page_type_text_comment_and_tags() -> None:
    markdown = ann.to_markdown(
        [
            ann.build(
                "A", "P", "highlight", text="the claim", comment="check", page="3", tags=["x", "y"]
            ),
            ann.build("B", "P", "image", page=""),
            ann.build("C", "P", "note", comment="remember this"),
        ]
    )
    assert markdown == (
        "## Annotations\n"
        "\n"
        '- **p. 3, highlight:** "the claim"\n'
        "  - Comment: check\n"
        "  - Tags: x, y\n"
        "- **image:** (image)\n"
        "- **note:** (note)\n"
        "  - Comment: remember this\n"
    )


def test_markdown_flattens_line_breaks_and_removes_control_characters() -> None:
    markdown = ann.to_markdown(
        [ann.build("A", "P", "highlight", text="line one\nline\ttwo\x1b[31m", comment="a\r\nb")]
    )
    assert '- **highlight:** "line one line two[31m"' in markdown
    assert "  - Comment: a b" in markdown
    assert "\x1b" not in markdown
