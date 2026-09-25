import argparse
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.cli.commands.slr.load_cmd import LoadCommand


@pytest.fixture
def mock_deps():
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_csv_inbound_service") as mi,
        patch("zotero_cli.infra.factory.GatewayFactory.get_collection_service") as mc,
    ):
        yield mi.return_value, mc.return_value


def test_load_command_execute_dry_run(mock_deps, capsys):
    mock_service, mock_coll = mock_deps
    mock_service.enrich_from_csv.return_value = {
        "total_rows": 10,
        "matched": 8,
        "unmatched": [9, 10],
        "updated": 0,
        "created": 0,
        "skipped": 8,
    }

    args = argparse.Namespace(
        file="test.csv",
        reviewer="Chicout",
        phase="QA",
        force=False,
        col_key=None,
        col_vote="Decision",
        col_reason=None,
        col_code=None,
        col_doi=None,
        col_title=None,
        col_evidence=None,
        move_to_included=None,
        move_to_excluded=None,
        user=False,
    )

    LoadCommand.execute(MagicMock(), args)

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
        file="missing.csv",
        reviewer="A",
        phase="P",
        force=True,
        col_key=None,
        col_vote=None,
        col_reason=None,
        col_code=None,
        col_doi=None,
        col_title=None,
        col_evidence=None,
        move_to_included=None,
        move_to_excluded=None,
        user=False,
    )

    LoadCommand.execute(MagicMock(), args)
    out = capsys.readouterr().out
    assert "Error: File not found" in out


def _load_args(**kw):
    base = dict(
        file="decisions.csv",
        reviewer="A",
        phase="title_abstract",
        execute=False,
        force=False,
        col_key=None,
        col_vote=None,
        col_reason=None,
        col_code=None,
        col_doi=None,
        col_title=None,
        col_evidence=None,
        move_to_included=None,
        move_to_excluded=None,
        user=False,
    )
    base.update(kw)
    return argparse.Namespace(**base)


_RESULTS = {"total_rows": 1, "matched": 1, "unmatched": [], "updated": 1, "created": 0}


def test_execute_applies(mock_deps, capsys):
    mock_service, _ = mock_deps
    mock_service.enrich_from_csv.return_value = _RESULTS

    LoadCommand.execute(MagicMock(), _load_args(execute=True))

    kwargs = mock_service.enrich_from_csv.call_args.kwargs
    assert kwargs["dry_run"] is False and kwargs["force"] is True
    assert "deprecated" not in capsys.readouterr().err


def test_force_still_applies_but_warns(mock_deps, capsys):
    """Issue #378: --force meant 'apply' here but 'skip the prompt'
    elsewhere. It keeps applying for now so scripts don't silently become
    dry runs, with a deprecation warning."""
    mock_service, _ = mock_deps
    mock_service.enrich_from_csv.return_value = _RESULTS

    LoadCommand.execute(MagicMock(), _load_args(force=True))

    assert mock_service.enrich_from_csv.call_args.kwargs["dry_run"] is False
    assert "--execute" in capsys.readouterr().err


def test_default_is_a_preview(mock_deps, capsys):
    mock_service, _ = mock_deps
    mock_service.enrich_from_csv.return_value = _RESULTS

    LoadCommand.execute(MagicMock(), _load_args())

    assert mock_service.enrich_from_csv.call_args.kwargs["dry_run"] is True
    assert "Re-run with --execute" in capsys.readouterr().out
