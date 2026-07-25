import argparse
from unittest.mock import MagicMock, patch

from zotero_cli.cli.commands.item_cmd import ItemCommand
from zotero_cli.core.services.merge_service import (
    FieldConflict,
    MergeResult,
    PlanExecutionResult,
)


def _args(master="M1", duplicates="D1", execute=False, force=False):
    return argparse.Namespace(
        verb="merge",
        master=master,
        duplicates=duplicates,
        from_plan=None,
        execute=execute,
        force=force,
        user=False,
    )


def _plan_args(from_plan, execute=False, force=False):
    return argparse.Namespace(
        verb="merge",
        master=None,
        duplicates=None,
        from_plan=from_plan,
        execute=execute,
        force=force,
        user=False,
    )


def test_item_merge_dry_run_shows_preview_and_does_not_call_execute(capsys):
    service = MagicMock()
    service.detect_conflicts.return_value = []
    preview = MergeResult(
        success=True,
        dry_run=True,
        master_key="M1",
        tags_added=2,
        collections_added=1,
        notes_moved=1,
        attachments_moved=3,
    )
    service.merge.return_value = preview

    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_merge_service", return_value=service
    ), patch(
        "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=MagicMock()
    ):
        ItemCommand().execute(_args(execute=False))

    assert service.merge.call_count == 1
    assert service.merge.call_args.kwargs["dry_run"] is True
    out = capsys.readouterr().out
    assert "Preview only" in out
    assert "M1" in out


def test_item_merge_execute_confirms_then_merges(capsys):
    service = MagicMock()
    service.detect_conflicts.return_value = []
    preview = MergeResult(success=True, dry_run=True, master_key="M1")
    final = MergeResult(success=True, dry_run=False, master_key="M1", merged_keys=["D1"])
    service.merge.side_effect = [preview, final]

    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_merge_service", return_value=service),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=MagicMock()),
        patch("rich.prompt.Confirm.ask", return_value=True),
    ):
        ItemCommand().execute(_args(execute=True, force=False))

    assert service.merge.call_count == 2
    assert service.merge.call_args_list[0].kwargs["dry_run"] is True
    assert service.merge.call_args_list[1].kwargs["dry_run"] is False
    out = capsys.readouterr().out
    assert "Merged 1 duplicate(s)" in out


def test_item_merge_execute_aborts_without_confirmation(capsys):
    service = MagicMock()
    service.detect_conflicts.return_value = []
    preview = MergeResult(success=True, dry_run=True, master_key="M1")
    service.merge.return_value = preview

    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_merge_service", return_value=service),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=MagicMock()),
        patch("rich.prompt.Confirm.ask", return_value=False),
    ):
        ItemCommand().execute(_args(execute=True, force=False))

    # Only the preview call - the real (dry_run=False) merge must never run.
    assert service.merge.call_count == 1
    out = capsys.readouterr().out
    assert "Aborted" in out


def test_item_merge_force_skips_confirmation(capsys):
    service = MagicMock()
    service.detect_conflicts.return_value = []
    preview = MergeResult(success=True, dry_run=True, master_key="M1")
    final = MergeResult(success=True, dry_run=False, master_key="M1", merged_keys=["D1"])
    service.merge.side_effect = [preview, final]

    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_merge_service", return_value=service),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=MagicMock()),
        patch("rich.prompt.Confirm.ask") as mock_confirm,
    ):
        ItemCommand().execute(_args(execute=True, force=True))

    mock_confirm.assert_not_called()
    assert service.merge.call_count == 2


def test_item_merge_prompts_for_each_conflict(capsys):
    service = MagicMock()
    service.detect_conflicts.return_value = [
        FieldConflict(field_name="title", values={"M1": "Title A", "D1": "Title B"})
    ]
    preview = MergeResult(success=True, dry_run=True, master_key="M1")
    service.merge.return_value = preview

    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_merge_service", return_value=service),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=MagicMock()),
        patch("rich.prompt.Prompt.ask", return_value="Title A") as mock_prompt,
    ):
        ItemCommand().execute(_args(execute=False))

    mock_prompt.assert_called_once()
    resolutions = service.merge.call_args.kwargs["field_resolutions"]
    assert resolutions == {"title": "Title A"}


def test_item_merge_preview_reports_unresolved_conflict_error(capsys):
    service = MagicMock()
    service.detect_conflicts.return_value = []
    preview = MergeResult(
        success=False,
        dry_run=True,
        master_key="M1",
        errors=["1 field conflict(s) require an explicit resolution before this merge can proceed."],
    )
    service.merge.return_value = preview

    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_merge_service", return_value=service
    ), patch(
        "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=MagicMock()
    ):
        ItemCommand().execute(_args(execute=False))

    out = capsys.readouterr().out
    assert "field conflict" in out
    # No second (real) merge attempt when the preview itself failed.
    assert service.merge.call_count == 1


def test_item_merge_errors_when_neither_single_group_nor_plan_given(capsys):
    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=MagicMock()
    ):
        ItemCommand().execute(argparse.Namespace(
            verb="merge", master=None, duplicates=None, from_plan=None,
            execute=False, force=False, user=False,
        ))

    out = capsys.readouterr().out
    assert "Provide either" in out


def test_item_merge_from_plan_missing_file_reports_error(capsys, tmp_path):
    missing = tmp_path / "does_not_exist.csv"
    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=MagicMock()
    ):
        ItemCommand().execute(_plan_args(str(missing)))

    out = capsys.readouterr().out
    assert "not found" in out


def test_item_merge_from_plan_dry_run_shows_preview(capsys, tmp_path):
    csv_path = tmp_path / "plan.csv"
    csv_path.write_text(
        "group_id,match_type,identifier,key,collection_id,title,role,reason\n"
        "doi:10.1/x,doi,10.1/x,M1,C1,Master,MASTER,Same DOI\n"
        "doi:10.1/x,doi,10.1/x,D1,C2,Dup,MERGE,Same DOI\n",
        encoding="utf-8",
    )

    service = MagicMock()
    preview = PlanExecutionResult(success=True, dry_run=True, group_results=[])
    service.execute_plan.return_value = preview

    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_merge_service", return_value=service),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=MagicMock()),
    ):
        ItemCommand().execute(_plan_args(str(csv_path), execute=False))

    assert service.execute_plan.call_count == 1
    assert service.execute_plan.call_args.kwargs["dry_run"] is True
    out = capsys.readouterr().out
    assert "Preview only" in out
    assert "doi:10.1/x" in out


def test_item_merge_from_plan_reports_incomplete_groups_without_executing(capsys, tmp_path):
    csv_path = tmp_path / "plan.csv"
    csv_path.write_text(
        "group_id,match_type,identifier,key,collection_id,title,role,reason\n"
        "doi:10.1/x,doi,10.1/x,M1,C1,Master,,\n"
        "doi:10.1/x,doi,10.1/x,D1,C2,Dup,,\n",
        encoding="utf-8",
    )

    service = MagicMock()
    preview = PlanExecutionResult(
        success=False, dry_run=True, errors=["Group 'doi:10.1/x' has no decision."]
    )
    service.execute_plan.return_value = preview

    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_merge_service", return_value=service),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=MagicMock()),
    ):
        ItemCommand().execute(_plan_args(str(csv_path), execute=True))

    assert service.execute_plan.call_count == 1  # only the preview call
    out = capsys.readouterr().out
    assert "incomplete" in out.lower()
    assert "has no decision" in out


def test_item_merge_from_plan_execute_confirms_then_runs(capsys, tmp_path):
    csv_path = tmp_path / "plan.csv"
    csv_path.write_text(
        "group_id,match_type,identifier,key,collection_id,title,role,reason\n"
        "doi:10.1/x,doi,10.1/x,M1,C1,Master,MASTER,Same DOI\n"
        "doi:10.1/x,doi,10.1/x,D1,C2,Dup,MERGE,Same DOI\n",
        encoding="utf-8",
    )

    service = MagicMock()
    preview = PlanExecutionResult(success=True, dry_run=True, group_results=[])
    final = PlanExecutionResult(
        success=True,
        dry_run=False,
        group_results=[MergeResult(success=True, dry_run=False, master_key="M1", merged_keys=["D1"])],
    )
    service.execute_plan.side_effect = [preview, final]

    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_merge_service", return_value=service),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway", return_value=MagicMock()),
        patch("rich.prompt.Confirm.ask", return_value=True),
    ):
        ItemCommand().execute(_plan_args(str(csv_path), execute=True))

    assert service.execute_plan.call_count == 2
    assert service.execute_plan.call_args_list[0].kwargs["dry_run"] is True
    assert service.execute_plan.call_args_list[1].kwargs["dry_run"] is False
    out = capsys.readouterr().out
    assert "Merged 1/1 group(s)" in out
