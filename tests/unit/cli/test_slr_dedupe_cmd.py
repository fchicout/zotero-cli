import argparse
from unittest.mock import MagicMock, patch

from zotero_cli.cli.commands.slr.dedupe_cmd import DedupeCommand
from zotero_cli.core.services.merge_service import MergeResult, PlanExecutionResult
from zotero_cli.core.services.slr.dedupe_service import (
    ClassifiedDuplicateGroup,
    OccurrenceScreening,
)


def _args(sources=None, export_plan=None, execute=False, force=False):
    return argparse.Namespace(
        sources=sources, export_plan=export_plan, execute=execute, force=force, user=False
    )


def _matching_group():
    return ClassifiedDuplicateGroup(
        match_type="doi",
        identifier="10.1/x",
        sdb_status="MATCHING",
        occurrences=[
            OccurrenceScreening(key="A", collection_id="C1", title="T", decisions=["accepted"]),
            OccurrenceScreening(key="B", collection_id="C2", title="T", decisions=["accepted"]),
        ],
    )


def _conflicting_group():
    return ClassifiedDuplicateGroup(
        match_type="doi",
        identifier="10.2/y",
        sdb_status="CONFLICTING",
        occurrences=[
            OccurrenceScreening(key="C", collection_id="C1", title="T2", decisions=["accepted"]),
            OccurrenceScreening(key="D", collection_id="C2", title="T2", decisions=["rejected"]),
        ],
    )


def test_dedupe_no_duplicates_found(capsys):
    service = MagicMock()
    service.warnings = []
    service.find_and_classify.return_value = []

    gateway = MagicMock()
    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_slr_dedupe_service", return_value=service
    ):
        DedupeCommand.execute(gateway, _args())

    assert "No duplicates found" in capsys.readouterr().out


def test_dedupe_preview_reports_counts_and_does_not_execute(capsys):
    service = MagicMock()
    service.warnings = []
    service.find_and_classify.return_value = [_matching_group(), _conflicting_group()]
    from zotero_cli.core.services.merge_service import MergePlan, MergePlanEntry

    service.build_reconciliation_plan.return_value = MergePlan(
        entries=[
            MergePlanEntry(
                group_id="g1",
                match_type="doi",
                identifier="10.1/x",
                occurrences=[],
                decision=MagicMock(master_key="A", merge_keys=["B"], reason="auto"),
            ),
            MergePlanEntry(
                group_id="g2", match_type="doi", identifier="10.2/y", occurrences=[], decision=None
            ),
        ]
    )

    gateway = MagicMock()
    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_slr_dedupe_service", return_value=service
    ):
        DedupeCommand.execute(gateway, _args())

    out = capsys.readouterr().out
    assert "1 group(s) auto-resolvable" in out
    assert "1 group(s) need manual review" in out
    service.execute_reconciliation.assert_not_called()


def test_dedupe_export_plan_writes_file(tmp_path, capsys):
    service = MagicMock()
    service.warnings = []
    service.find_and_classify.return_value = [_matching_group()]
    from zotero_cli.core.services.duplicate_service import DuplicateOccurrence
    from zotero_cli.core.services.merge_service import MergeDecision, MergePlan, MergePlanEntry

    service.build_reconciliation_plan.return_value = MergePlan(
        entries=[
            MergePlanEntry(
                group_id="doi:10.1/x",
                match_type="doi",
                identifier="10.1/x",
                occurrences=[
                    DuplicateOccurrence(key="A", collection_id="C1", title="T"),
                    DuplicateOccurrence(key="B", collection_id="C2", title="T"),
                ],
                decision=MergeDecision(master_key="A", merge_keys=["B"], reason="auto"),
            )
        ]
    )

    out_file = str(tmp_path / "plan.csv")
    gateway = MagicMock()
    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_slr_dedupe_service", return_value=service
    ):
        DedupeCommand.execute(gateway, _args(export_plan=out_file))

    content = open(out_file, encoding="utf-8").read()
    assert "group_id" in content
    assert "A" in content and "B" in content
    assert "Exported reconciliation plan" in capsys.readouterr().out


def test_dedupe_execute_merges_resolved_groups_after_confirmation(capsys):
    service = MagicMock()
    service.warnings = []
    service.find_and_classify.return_value = [_matching_group(), _conflicting_group()]
    from zotero_cli.core.services.merge_service import MergeDecision, MergePlan, MergePlanEntry

    service.build_reconciliation_plan.return_value = MergePlan(
        entries=[
            MergePlanEntry(
                group_id="g1",
                match_type="doi",
                identifier="10.1/x",
                occurrences=[],
                decision=MergeDecision(master_key="A", merge_keys=["B"], reason="auto"),
            ),
            MergePlanEntry(
                group_id="g2", match_type="doi", identifier="10.2/y", occurrences=[], decision=None
            ),
        ]
    )
    service.execute_reconciliation.side_effect = [
        PlanExecutionResult(
            success=True,
            dry_run=True,
            group_results=[
                MergeResult(success=True, dry_run=True, master_key="A", merged_keys=["B"])
            ],
        ),
        PlanExecutionResult(
            success=True,
            dry_run=False,
            group_results=[
                MergeResult(success=True, dry_run=False, master_key="A", merged_keys=["B"])
            ],
        ),
    ]

    gateway = MagicMock()
    with (
        patch(
            "zotero_cli.infra.factory.GatewayFactory.get_slr_dedupe_service", return_value=service
        ),
        patch("zotero_cli.cli.commands.slr.dedupe_cmd.Confirm.ask", return_value=True),
    ):
        DedupeCommand.execute(gateway, _args(execute=True))

    out = capsys.readouterr().out
    assert "Merged 1 duplicate item(s)" in out
    assert "1 group(s) still need manual review" in out
    assert service.execute_reconciliation.call_count == 2


def test_dedupe_execute_aborts_without_confirmation(capsys):
    service = MagicMock()
    service.warnings = []
    service.find_and_classify.return_value = [_matching_group()]
    from zotero_cli.core.services.merge_service import MergeDecision, MergePlan, MergePlanEntry

    service.build_reconciliation_plan.return_value = MergePlan(
        entries=[
            MergePlanEntry(
                group_id="g1",
                match_type="doi",
                identifier="10.1/x",
                occurrences=[],
                decision=MergeDecision(master_key="A", merge_keys=["B"], reason="auto"),
            ),
        ]
    )
    service.execute_reconciliation.return_value = PlanExecutionResult(
        success=True,
        dry_run=True,
        group_results=[MergeResult(success=True, dry_run=True, master_key="A", merged_keys=["B"])],
    )

    gateway = MagicMock()
    with (
        patch(
            "zotero_cli.infra.factory.GatewayFactory.get_slr_dedupe_service", return_value=service
        ),
        patch("zotero_cli.cli.commands.slr.dedupe_cmd.Confirm.ask", return_value=False),
    ):
        DedupeCommand.execute(gateway, _args(execute=True))

    assert "Aborted. Nothing written." in capsys.readouterr().out
    assert service.execute_reconciliation.call_count == 1  # only the preview call


def test_dedupe_execute_with_all_conflicting_reports_nothing_to_merge(capsys):
    service = MagicMock()
    service.warnings = []
    service.find_and_classify.return_value = [_conflicting_group()]
    from zotero_cli.core.services.merge_service import MergePlan, MergePlanEntry

    service.build_reconciliation_plan.return_value = MergePlan(
        entries=[
            MergePlanEntry(
                group_id="g1", match_type="doi", identifier="10.2/y", occurrences=[], decision=None
            ),
        ]
    )

    gateway = MagicMock()
    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_slr_dedupe_service", return_value=service
    ):
        DedupeCommand.execute(gateway, _args(execute=True))

    assert "No auto-resolvable groups" in capsys.readouterr().out
    service.execute_reconciliation.assert_not_called()
