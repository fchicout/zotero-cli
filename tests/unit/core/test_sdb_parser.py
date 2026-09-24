from zotero_cli.core.utils.sdb_parser import parse_sdb_note


def test_encoded_note_round_trips_html_special_characters():
    """A '<' or '>' in a free-text field used to reach Zotero's note
    sanitizer as HTML, which could drop or rewrite part of the record."""
    from zotero_cli.core.utils.sdb_parser import decode_json_note, encode_json_note

    data = {
        "action": "screening_decision",
        "sdb_version": "1.2",
        "reason": "n < 30 & effect > 0.5 <script>alert(1)</script> </div><div>",
        "evidence": 'quote "kept"',
    }
    note = encode_json_note(data)
    body = note[len("<div>") : -len("</div>")]
    assert "<" not in body and ">" not in body
    assert '"evidence"' in body  # JSON quotes stay readable
    assert decode_json_note(note) == data
    assert parse_sdb_note(note) == data


def test_legacy_unescaped_notes_still_parse():
    legacy = '<div>{"action": "screening_decision", "decision": "accepted"}</div>'
    parsed = parse_sdb_note(legacy)
    assert parsed is not None and parsed["decision"] == "accepted"
