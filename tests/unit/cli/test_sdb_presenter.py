from zotero_cli.cli.presenters.sdb_presenter import build_inspect_table


def test_build_inspect_table():
    entries = [
        {
            "decision": "accepted",
            "persona": "P1",
            "phase": "ph1",
            "audit_version": "1.2",
            "timestamp": "2026-01-01",
        }
    ]
    table = build_inspect_table("ITEM1", entries)
    assert table.title == "SDB Inspect: ITEM1"
    assert len(table.rows) == 1


def test_reason_text_is_shortened_and_markup_in_decision_is_escaped():
    entries = [{"decision": "[bold]x", "reason_code": ["EC1"], "reason_text": "r" * 50}]
    table = build_inspect_table("K", entries)
    reason_cells = list(table.columns[1].cells)
    assert reason_cells == ["EC1 (" + "r" * 30 + "...)"]
