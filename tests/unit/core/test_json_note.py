import json

import pytest

from zotero_cli.core.utils.json_note import decode_json_note


def test_decodes_json_in_a_div():
    assert decode_json_note('<div>{"a": 1, "b": [2, 3]}</div>') == {"a": 1, "b": [2, 3]}


def test_decodes_html_escaped_json():
    body = '<div>{"reason": "a &lt; b &amp; c"}</div>'

    assert decode_json_note(body) == {"reason": "a < b & c"}


def test_decodes_multi_line_json():
    body = "<div>" + json.dumps({"k": "v"}, indent=2) + "</div>"

    assert decode_json_note(body) == {"k": "v"}


@pytest.mark.parametrize("content", ["", "<p>just a note</p>", "<div>{not json}</div>"])
def test_a_note_without_a_json_object_is_left_as_text(content):
    assert decode_json_note(content) is None
