import argparse
from unittest.mock import patch

import pytest

from zotero_cli.cli.commands.slr.load_cmd import LoadCommand


@pytest.fixture
def mock_deps():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_csv_inbound_service") as mi, \
         patch("zotero_cli.infra.factory.GatewayFactory.get_collection_service") as mc:
        yield mi.return_value, mc.return_value

def test_load_command_execute_dry_run(mock_deps, capsys):
    mock_service, mock_coll = mock_deps
    mock_service.enrich_from_csv.return_value = {
        "total_rows": 10,
        "matched": 8,
        "unmatched": [9, 10],
        "updated": 0,
        "created": 0,
        "skipped": 8
    }

    args = argparse.Namespace(
        file="test.csv", reviewer="Chicout", phase="QA", force=False,
        col_key=None, col_vote="Decision", col_reason=None, col_code=None,
        col_doi=None, col_title=None, col_evidence=None,
        move_to_included=None, move_to_excluded=None, user=False
    )

    LoadCommand.execute(None, args)

    out = capsys.readouterr().out
    assert "Import CSV Results" in out
    assert "matched" in out.lower()

    mock_service.enrich_from_csv.assert_called_once()
    kwargs = mock_service.enrich_from_csv.call_args.kwargs
    assert kwargs["reviewer"] == "Chicout"
    assert kwargs["dry_run"] is True
    assert kwargs["column_map"] == {"vote": "Decision"}

def test_load_command_error(mock_deps, capsys):
    mock_service, mock_coll = mock_deps
    mock_service.enrich_from_csv.return_value = {"error": "File not found"}

    args = argparse.Namespace(
        file="missing.csv", reviewer="A", phase="P", force=True,
        col_key=None, col_vote=None, col_reason=None, col_code=None,
        col_doi=None, col_title=None, col_evidence=None,
        move_to_included=None, move_to_excluded=None, user=False
    )

    LoadCommand.execute(None, args)
    out = capsys.readouterr().out
    assert "Error: File not found" in out
