import csv
import io
import json

from zotero_cli.cli.presenters import item_list_presenter as p
from zotero_cli.core.utils.terminal_safety import SafeConsole as Console
from zotero_cli.core.zotero_item import ZoteroItem


def _item(key="K1", **data):
    base = {
        "itemType": "journalArticle",
        "title": "A Study",
        "date": "2023-05-01",
        "DOI": "10.1/abc",
        "creators": [
            {"creatorType": "author", "firstName": "Gabriel", "lastName": "Silva"},
            {"creatorType": "author", "firstName": "Ana", "lastName": "Costa"},
        ],
        "publicationTitle": "Journal of Tests",
        "tags": [{"tag": "rsl:include"}, {"tag": "ml"}],
    }
    base.update(data)
    return ZoteroItem.from_raw_zotero_item({"key": key, "data": base})


def test_default_fields_preserve_existing_columns():
    assert p.parse_fields(None) == ["key", "title", "type"]


def test_wide_preset():
    assert p.parse_fields(None, wide=True) == [
        "key",
        "title",
        "first_author",
        "year",
        "venue",
        "doi",
    ]


def test_parse_fields_is_case_insensitive_for_known_names_but_keeps_raw_names():
    assert p.parse_fields(" Key, TITLE ,publicationTitle,,DOI ") == [
        "key",
        "title",
        "publicationTitle",
        "doi",
    ]


def test_resolve_known_and_derived_fields():
    item = _item()
    assert p.resolve_field(item, "creators") == ["Silva, Gabriel", "Costa, Ana"]
    assert p.resolve_field(item, "first_author") == "Silva et al."
    assert p.resolve_field(item, "year") == "2023"
    assert p.resolve_field(item, "venue") == "Journal of Tests"
    assert p.resolve_field(item, "tags") == ["rsl:include", "ml"]


def test_first_author_single_author_has_no_et_al():
    item = _item(creators=[{"creatorType": "author", "name": "OpenAI Consortium"}])
    assert p.resolve_field(item, "first_author") == "OpenAI Consortium"


def test_venue_falls_back_across_item_types():
    paper = _item(itemType="conferencePaper", publicationTitle="", proceedingsTitle="Proc. X")
    assert p.resolve_field(paper, "venue") == "Proc. X"


def test_raw_zotero_fields_resolve_including_case_differences():
    item = _item(volume="12", ISSN="1234-5678")
    assert p.resolve_field(item, "volume") == "12"
    assert p.resolve_field(item, "issn") == "1234-5678"
    assert p.resolve_field(item, "notAField") == ""


def test_unknown_fields_reports_only_raw_names_no_item_has():
    items = [_item(volume="12")]
    assert p.unknown_fields(items, ["key", "volume", "volumne"]) == ["volumne"]


def test_json_output_keeps_lists_structured():
    out = io.StringIO()
    p.render_json([_item()], ["key", "creators", "year"], out)
    assert json.loads(out.getvalue()) == [
        {"key": "K1", "creators": ["Silva, Gabriel", "Costa, Ana"], "year": "2023"}
    ]


def test_csv_output_flattens_lists_and_guards_formula_injection():
    """Issue #237: item fields are collaborator-controlled, so a title
    like "=HYPERLINK(...)" must not reach a spreadsheet as a formula."""
    out = io.StringIO()
    p.render_csv([_item(title='=HYPERLINK("http://evil")')], ["key", "title", "creators"], out)
    rows = list(csv.reader(io.StringIO(out.getvalue())))
    assert rows[0] == ["key", "title", "creators"]
    assert rows[1][1].startswith("'=")
    assert rows[1][2] == "Silva, Gabriel; Costa, Ana"


def test_markdown_output_escapes_pipes_and_newlines():
    out = io.StringIO()
    p.render_markdown([_item(title="A | B\nC")], ["key", "title"], out)
    lines = out.getvalue().splitlines()
    assert lines[0] == "| Key | Title |"
    assert lines[1] == "| --- | --- |"
    assert lines[2] == "| K1 | A \\| B C |"


def test_table_renders_bracketed_titles_literally():
    """Issue #253: "[Retracted]" must not be swallowed as Rich markup."""
    console = Console(file=io.StringIO(), width=200)
    p.render_table([_item(title="[Retracted] A Study")], ["key", "title"], "Items", console)
    output = console.file.getvalue()  # type: ignore[attr-defined]
    assert "[Retracted] A Study" in output
    assert "Showing 1 items." in output


# GHSA-3r38-p632-f79q: CSV and Markdown go straight to the terminal, so a
# collaborator-controlled title must not carry escape sequences through.
HOSTILE_TITLE = "Evil \x1b]8;;https://attacker.example\x07click\x1b]8;;\x07 \x1b[31mred\x9b2J ‮txt.exe"


def _hostile_output(render) -> str:
    out = io.StringIO()
    render([_item(title=HOSTILE_TITLE)], ["key", "title"], out)
    return out.getvalue()


def test_csv_strips_terminal_controls():
    text = _hostile_output(p.render_csv)
    assert "\x1b" not in text and "\x07" not in text and "\x9b" not in text and "‮" not in text
    assert "click" in text and "red" in text


def test_markdown_strips_terminal_controls():
    text = _hostile_output(p.render_markdown)
    assert "\x1b" not in text and "\x07" not in text and "\x9b" not in text and "‮" not in text
    assert "click" in text


def test_json_escapes_c0_controls():
    """JSON keeps data values as they are, but its encoding escapes C0
    controls (ESC, BEL), so they don't reach the terminal raw."""
    text = _hostile_output(p.render_json)
    assert "\x1b" not in text and "\x07" not in text
    assert "\\u001b" in text
