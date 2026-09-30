"""Issue #402: `--trash` on the bulk deletes - recoverable instead of permanent."""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.cli.commands.collection_cmd import CollectionCommand
from zotero_cli.cli.commands.item_cmd import ItemCommand
from zotero_cli.cli.commands.slr.dedupe_cmd import DedupeCommand
from zotero_cli.cli.main import build_parser
from zotero_cli.core.exceptions import UsageError
from zotero_cli.core.services.collection_service import RecursiveDeletePlan, RecursiveDeleteResult
from zotero_cli.core.services.merge_service import (
    MergeDecision,
    MergePlan,
    MergePlanEntry,
    MergeResult,
    PlanExecutionResult,
)
from zotero_cli.core.zotero_item import ZoteroItem


def _flat(text: str) -> str:
    """Rich wraps to the terminal width; compare words, not line breaks."""
    return " ".join(text.split())


TRASH_FLAGS = [
    ["collection", "delete", "--key", "C", "--recursive", "--trash"],
    ["item", "merge", "--master", "M", "--duplicates", "D", "--trash"],
    ["item", "transfer", "--key", "K", "--target-group", "1", "--delete-source", "--trash"],
    ["slr", "dedupe", "--trash"],
]


@pytest.mark.parametrize("argv", TRASH_FLAGS)
def test_trash_flag_is_accepted_and_off_by_default(argv):
    assert build_parser().parse_args(argv).trash is True
    assert build_parser().parse_args([a for a in argv if a != "--trash"]).trash is False


# ---- collection delete --recursive --trash --------------------------------------


def _delete_args(**kw):
    base = dict(
        verb="delete", key="COL_KEY", version=None, recursive=True, execute=True, yes=True,
        include_shared=False, trash=True, user=False,
    )
    base.update(kw)
    return argparse.Namespace(**base)


def _plan():
    item = ZoteroItem(key="I1", version=1, item_type="journalArticle", title="Only here")
    return RecursiveDeletePlan(
        root_key="COL_KEY", collections=[("COL_KEY", 42, "Root")], items_to_delete=[item]
    )


def _run_collection_delete(args, result=None):
    service = MagicMock()
    service.plan_recursive_delete.return_value = _plan()
    service.execute_recursive_delete.return_value = result or RecursiveDeleteResult(
        deleted_items=1, deleted_collections=1
    )
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as gateway,
        patch("zotero_cli.infra.factory.GatewayFactory.get_collection_service", return_value=service),
    ):
        gateway.return_value.get_collection_id_by_name.return_value = "COL_KEY"
        gateway.return_value.get_collection.return_value = {"version": 42}
        CollectionCommand().execute(args)
    return service


def test_recursive_delete_trash_passes_trash_and_says_what_is_permanent(capsys):
    service = _run_collection_delete(_delete_args())

    service.execute_recursive_delete.assert_called_once_with(
        service.plan_recursive_delete.return_value, include_shared=False, trash=True
    )
    out = _flat(capsys.readouterr().out)
    assert "move the items to the trash and permanently delete the collections" in out
    assert "the collections are deleted for good" in out
    assert "Trashed 1 item(s) and deleted 1 collection(s)." in out
    assert "bypasses Zotero's trash" not in out


def test_recursive_delete_trash_preview_changes_nothing(capsys):
    service = _run_collection_delete(_delete_args(execute=False, yes=False))

    service.execute_recursive_delete.assert_not_called()
    assert "Preview only" in capsys.readouterr().out


def test_recursive_delete_without_trash_is_still_permanent(capsys):
    service = _run_collection_delete(_delete_args(trash=False))

    assert service.execute_recursive_delete.call_args.kwargs["trash"] is False
    out = _flat(capsys.readouterr().out)
    assert "bypasses Zotero's trash" in out
    assert "Deleted 1 item(s) and 1 collection(s)." in out


def test_trash_needs_recursive_on_collection_delete():
    command = CollectionCommand()
    args = _delete_args(recursive=False)
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as gateway:
        gateway.return_value.get_collection_id_by_name.return_value = "COL_KEY"
        gateway.return_value.get_collection.return_value = {"version": 1}
        with pytest.raises(UsageError, match="needs --recursive"):
            command.execute(args)


# ---- item merge --trash -----------------------------------------------------------


def _merge_args(**kw):
    base = dict(
        verb="merge", master="M1", duplicates="D1", from_plan=None, execute=True, force=True,
        trash=True, user=False,
    )
    base.update(kw)
    return argparse.Namespace(**base)


def test_item_merge_trash_reaches_the_service_and_the_wording(capsys):
    service = MagicMock()
    service.detect_conflicts.return_value = []
    service.merge.side_effect = [
        MergeResult(success=True, dry_run=True, master_key="M1"),
        MergeResult(success=True, dry_run=False, master_key="M1", merged_keys=["D1"]),
    ]
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_merge_service", return_value=service),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=MagicMock()),
    ):
        ItemCommand().execute(_merge_args())

    assert service.merge.call_args_list[1].kwargs["trash"] is True
    assert "Merged 1 duplicate(s)" in capsys.readouterr().out


def test_item_merge_trash_preview_says_recoverable(capsys):
    service = MagicMock()
    service.detect_conflicts.return_value = []
    service.merge.return_value = MergeResult(success=True, dry_run=True, master_key="M1")
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_merge_service", return_value=service),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=MagicMock()),
    ):
        ItemCommand().execute(_merge_args(execute=False))

    out = _flat(capsys.readouterr().out)
    assert "go to Zotero's trash and can be restored" in out
    assert "PERMANENT" not in out


def test_item_merge_from_plan_passes_trash(tmp_path, capsys):
    plan_file = tmp_path / "plan.json"
    plan_file.write_text("{}")
    plan = MergePlan(
        entries=[
            MergePlanEntry(
                group_id="g1", match_type="doi", identifier="10.1/x", occurrences=[],
                decision=MergeDecision(master_key="M1", merge_keys=["D1"], reason="r"),
            )
        ]
    )
    service = MagicMock()
    service.execute_plan.return_value = PlanExecutionResult(
        success=True, dry_run=False,
        group_results=[MergeResult(success=True, dry_run=False, master_key="M1")],
    )
    args = _merge_args(master=None, duplicates=None, from_plan=str(plan_file))
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_merge_service", return_value=service),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=MagicMock()),
        patch("zotero_cli.core.services.merge_plan_io.parse_plan_from_json", return_value=plan),
    ):
        ItemCommand().execute(args)

    assert service.execute_plan.call_args_list[-1].kwargs["trash"] is True


# ---- item transfer --trash ---------------------------------------------------------


def _transfer_args(**kw):
    base = dict(
        verb="transfer", key="K1", target_group="123", delete_source=True, trash=True, user=False
    )
    base.update(kw)
    return argparse.Namespace(**base)


def _run_transfer(args, *, source_deleted=True):
    service = MagicMock()
    service.transfer_item.return_value = MagicMock(
        new_key="NEW1", copied_children=0, failures=[], source_deleted=source_deleted
    )
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"),
        patch("zotero_cli.core.config.get_config", return_value=MagicMock()),
        patch("dataclasses.replace", return_value=MagicMock()),
        patch("zotero_cli.infra.factory.GatewayFactory.get_transfer_service", return_value=service),
    ):
        ItemCommand().execute(args)
    return service


def test_item_transfer_trash_trashes_the_source(capsys):
    service = _run_transfer(_transfer_args())

    assert service.transfer_item.call_args.kwargs["trash_source"] is True
    assert "to the trash" in _flat(capsys.readouterr().out)


def test_item_transfer_delete_source_without_trash_still_deletes(capsys):
    service = _run_transfer(_transfer_args(trash=False))

    assert service.transfer_item.call_args.kwargs["trash_source"] is False
    assert "Deleted the source item K1." in capsys.readouterr().out


def test_item_transfer_trash_needs_delete_source():
    command = ItemCommand()
    args = _transfer_args(delete_source=False)
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"),
        patch("zotero_cli.core.config.get_config", return_value=MagicMock()),
        patch("dataclasses.replace", return_value=MagicMock()),
        patch("zotero_cli.infra.factory.GatewayFactory.get_transfer_service"),
    ):
        with pytest.raises(UsageError, match="needs --delete-source"):
            command.execute(args)


# ---- slr dedupe --trash --------------------------------------------------------------


def test_slr_dedupe_trash_reaches_the_reconciliation(capsys):
    from zotero_cli.core.services.slr.dedupe_service import (
        ClassifiedDuplicateGroup,
        OccurrenceScreening,
    )

    group = ClassifiedDuplicateGroup(
        match_type="doi", identifier="10.1/x", sdb_status="MATCHING",
        occurrences=[
            OccurrenceScreening(key="A", collection_id="C1", title="T", decisions=["accepted"]),
            OccurrenceScreening(key="B", collection_id="C2", title="T", decisions=["accepted"]),
        ],
    )
    service = MagicMock()
    service.warnings = []
    service.find_and_classify.return_value = [group]
    service.build_reconciliation_plan.return_value = MergePlan(
        entries=[
            MergePlanEntry(
                group_id="g1", match_type="doi", identifier="10.1/x", occurrences=[],
                decision=MergeDecision(master_key="A", merge_keys=["B"], reason="auto"),
            )
        ]
    )
    merged = MergeResult(success=True, dry_run=False, master_key="A", merged_keys=["B"])
    service.execute_reconciliation.side_effect = [
        PlanExecutionResult(success=True, dry_run=True, group_results=[merged]),
        PlanExecutionResult(success=True, dry_run=False, group_results=[merged]),
    ]
    args = argparse.Namespace(
        sources=None, export_plan=None, execute=True, force=True, trash=True, user=False
    )
    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_slr_dedupe_service", return_value=service
    ):
        DedupeCommand.execute(MagicMock(), args)

    assert service.execute_reconciliation.call_args_list[-1].kwargs["trash"] is True
    assert "to the trash" in _flat(capsys.readouterr().out)
