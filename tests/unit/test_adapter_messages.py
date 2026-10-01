"""Messages from the remaining services and adapters (Issue #393).

Each goes to the `notify` sink or the default one (what the CLI installs), never
straight to the terminal.
"""

import asyncio
import logging
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.core.utils.notify import set_default_notify


@pytest.fixture
def said() -> List[str]:
    messages: List[str] = []
    set_default_notify(messages.append)  # reset around every test by tests/unit/conftest.py
    return messages


def _silent(capsys):
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_audit_reports_an_unreadable_latex_file(said, capsys, tmp_path):
    from zotero_cli.core.services.audit_service import AuditService

    service = AuditService(MagicMock())
    directory = tmp_path / "paper.tex"
    directory.mkdir()  # exists, but cannot be read as a file

    assert service._get_citations_recursive(directory) == set()

    assert len(said) == 1
    assert said[0].startswith(f"Warning: Failed to read {directory}:")
    _silent(capsys)


def test_integrity_reports_an_item_whose_children_cannot_be_checked(said, capsys):
    from zotero_cli.core.services.slr.integrity import IntegrityService
    from zotero_cli.core.zotero_item import ZoteroItem

    gateway = MagicMock()
    gateway.get_collection_id_by_name.return_value = "C1"
    gateway.get_items_in_collection.return_value = iter(
        [ZoteroItem(key="K1", version=1, item_type="journalArticle", title="T")]
    )
    service = IntegrityService(gateway)
    service._audit_children = MagicMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]

    report = service.audit_collection("Col")

    assert report is not None
    assert said == ["Error checking children for item K1: boom"]
    _silent(capsys)


def test_csv_enrichment_lists_matches_in_a_dry_run(said, capsys, tmp_path):
    from zotero_cli.core.services.slr.csv_inbound import CSVInboundService
    from zotero_cli.core.zotero_item import ZoteroItem

    csv_file = tmp_path / "votes.csv"
    csv_file.write_text("Key,Vote,Reason,Code,Title\nK1,INCLUDE,,,Some paper\n", encoding="utf-8")
    gateway = MagicMock()
    gateway.search_items.return_value = iter(
        [ZoteroItem(key="K1", version=1, item_type="journalArticle", title="Some paper")]
    )
    service = CSVInboundService(gateway)

    results = service.enrich_from_csv(str(csv_file), reviewer="R", dry_run=True)

    assert results["skipped"] == 1
    assert said == ["[DRY RUN] Match: K1 | Some paper..."]
    _silent(capsys)


@pytest.mark.parametrize(
    ("module", "cls"),
    [
        ("zotero_cli.infra.ris_lib", "RisLibGateway"),
        ("zotero_cli.infra.bibtex_lib", "BibtexLibGateway"),
    ],
)
def test_file_gateways_report_a_failed_write(said, capsys, tmp_path, module, cls):
    import importlib

    gateway = getattr(importlib.import_module(module), cls)()
    target = tmp_path / "missing_dir" / "out.file"  # parent directory does not exist

    assert (
        gateway.write_file(str(target), [MagicMock(title="T", authors="A", year="2020")]) is False
    )

    assert len(said) == 1
    assert said[0].startswith("Error writing")
    _silent(capsys)


def test_a_broken_resolvers_file_is_a_warning(said, capsys, tmp_path):
    from zotero_cli.infra.resolver_factory import ResolverFactory

    (tmp_path / "resolvers.yaml").write_text("resolvers: [unclosed", encoding="utf-8")
    with patch("zotero_cli.core.config.get_config_path", return_value=tmp_path / "config.toml"):
        assert ResolverFactory.get_generic_resolvers() == []

    assert len(said) == 1
    assert said[0].startswith("Warning: Failed to load generic resolvers from")
    _silent(capsys)


def test_a_broken_resolvers_file_is_logged_without_a_sink(caplog, tmp_path):
    from zotero_cli.infra.resolver_factory import ResolverFactory

    (tmp_path / "resolvers.yaml").write_text("resolvers: [unclosed", encoding="utf-8")
    with (
        patch("zotero_cli.core.config.get_config_path", return_value=tmp_path / "config.toml"),
        caplog.at_level(logging.WARNING),
    ):
        ResolverFactory.get_generic_resolvers()

    # The adapter's own logger.warning follows the message, as it always did.
    assert {r.levelno for r in caplog.records} == {logging.WARNING}
    assert any("Failed to load generic resolvers" in r.getMessage() for r in caplog.records)


def test_serve_announces_the_gateway_startup(said, capsys):
    from fastapi import FastAPI

    from zotero_cli.api.main import lifespan

    async def start() -> None:
        async with lifespan(FastAPI()):
            pass

    with (
        patch("zotero_cli.api.main.get_config"),
        patch("zotero_cli.api.main.GatewayFactory"),
        patch("zotero_cli.api.main.set_gateway_instance"),
        patch("zotero_cli.api.main.set_job_queue_service_instance"),
    ):
        asyncio.run(start())

    assert said == ["Initializing Zotero Gateway..."]
    _silent(capsys)
