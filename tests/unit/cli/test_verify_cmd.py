import argparse
from unittest.mock import patch

import pytest

from zotero_cli.cli.commands.report_cmd import ReportCommand


@pytest.fixture
def mock_deps():
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_integrity_service") as mi,
        patch("zotero_cli.infra.factory.GatewayFactory.get_audit_service") as ma,
    ):
        yield mi.return_value, ma.return_value


def test_verify_collection_pass(mock_deps, capsys):
    mock_integrity, mock_audit = mock_deps
    from zotero_cli.core.services.slr.integrity import AuditReport

    report = AuditReport(total_items=1)
    mock_integrity.audit_collection.return_value = report

    args = argparse.Namespace(
        report_type="audit", collection="MyColl", verbose=False, export_missing=None, user=False
    )
    ReportCommand().execute(args)

    out = capsys.readouterr().out
    assert "Verification PASSED" in out


def test_verify_latex_pass(mock_deps, capsys):
    mock_integrity, mock_audit = mock_deps
    mock_audit.audit_manuscript.return_value = {
        "total_citations": 1,
        "items": {"K1": {"exists": True, "screened": True, "decision": "ACCEPTED", "title": "T1"}},
    }

    args = argparse.Namespace(report_type="verify-latex", latex="paper.tex", user=False)
    ReportCommand().execute(args)

    out = capsys.readouterr().out
    assert "Verification Success" in out
