"""The release smoke-test fixture builds a usable offline library (Issue #399)."""

import sqlite3

from scripts.build_smoke_fixture import build


def test_the_fixture_has_a_collection_and_a_papers_pdf_child(tmp_path):
    build(tmp_path)

    assert (tmp_path / "sample.pdf").read_bytes().startswith(b"%PDF")

    conn = sqlite3.connect(tmp_path / "zotero.sqlite")
    try:
        keys = {r[0] for r in conn.execute("SELECT key FROM items")}
        assert {"SMOKE001", "SMOKE002", "SMOKEPDF"} <= keys
        assert conn.execute(
            "SELECT collectionName FROM collections WHERE key = 'SMOKECOL'"
        ).fetchone() == ("Smoke Test",)
    finally:
        conn.close()


def test_the_fixture_works_through_the_offline_gateway(tmp_path):
    """What the release workflow actually runs the binary against."""
    from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

    build(tmp_path)
    gateway = SqliteZoteroGateway(str(tmp_path / "zotero.sqlite"))

    items = list(gateway.get_items_in_collection("SMOKECOL"))
    assert {i.key for i in items} == {"SMOKE001", "SMOKE002"}

    paper = gateway.get_item("SMOKE001")
    assert paper is not None
    assert "Lovelace" in paper.authors[0]
    children = gateway.get_item_children("SMOKE001")
    assert [c["key"] for c in children] == ["SMOKEPDF"]
