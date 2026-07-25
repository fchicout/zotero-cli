import argparse
from unittest.mock import MagicMock, patch

from zotero_cli.cli.commands.slr.report_cmd import SLRReportCommand
from zotero_cli.core.services.report_service import PrismaReport
from zotero_cli.core.services.slr.dedupe_service import (
    ClassifiedDuplicateGroup,
    OccurrenceScreening,
)


def _args(dedupe_source=None):
    return argparse.Namespace(
        report_verb="prisma",
        collection="My Collection",
        output_chart=None,
        verbose=False,
        dedupe_source=dedupe_source,
        user=False,
    )


def test_prisma_without_dedupe_source_skips_duplicate_detection(capsys):
    gateway = MagicMock()
    with patch(
        "zotero_cli.core.services.report_service.ReportService.generate_prisma_report",
        return_value=PrismaReport(collection_name="My Collection", total_items=10),
    ) as mock_gen:
        SLRReportCommand._handle_prisma(gateway, _args())

    mock_gen.assert_called_once_with("My Collection", duplicates_removed=0)


def test_prisma_with_dedupe_source_computes_duplicates_removed(capsys):
    gateway = MagicMock()
    gateway.get_collection_id_by_name.return_value = "COL_A"

    dedupe_service = MagicMock()
    dedupe_service.find_and_classify.return_value = [
        ClassifiedDuplicateGroup(
            match_type="doi",
            identifier="10.1/x",
            sdb_status="MATCHING",
            occurrences=[
                OccurrenceScreening(key="A", collection_id="COL_A"),
                OccurrenceScreening(key="B", collection_id="COL_A"),
                OccurrenceScreening(key="C", collection_id="COL_A"),
            ],
        )
    ]

    with (
        patch(
            "zotero_cli.infra.factory.GatewayFactory.get_slr_dedupe_service",
            return_value=dedupe_service,
        ),
        patch(
            "zotero_cli.core.services.report_service.ReportService.generate_prisma_report",
            return_value=PrismaReport(
                collection_name="My Collection", total_items=10, duplicates_removed=2
            ),
        ) as mock_gen,
    ):
        SLRReportCommand._handle_prisma(gateway, _args(dedupe_source="Source A"))

    dedupe_service.find_and_classify.assert_called_once_with(["COL_A"])
    mock_gen.assert_called_once_with("My Collection", duplicates_removed=2)
    assert "Duplicates Removed" in capsys.readouterr().out
