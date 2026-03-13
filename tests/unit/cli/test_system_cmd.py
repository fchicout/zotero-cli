import argparse
from unittest.mock import MagicMock, mock_open, patch

import pytest

from zotero_cli.cli.commands.system_cmd import InfoCommand, SystemCommand


@pytest.fixture
def system_cmd():
    return SystemCommand()


def test_info_command_execute(capsys):
    info_cmd = InfoCommand()
    args = argparse.Namespace(config=None)

    with patch("zotero_cli.core.config.get_config") as mock_get_config:
        mock_config = MagicMock()
        mock_config.library_id = "123"
        mock_config.library_type = "user"
        mock_config.api_key = "key"
        mock_config.openai_api_key = "okey"
        mock_config.gemini_api_key = "gkey"
        mock_config.target_group_url = None
        mock_get_config.return_value = mock_config

        info_cmd.execute(args)

    out, _ = capsys.readouterr()
    assert "Library ID:  123" in out
    assert "Library Type: user" in out
    assert "OpenAI API Key: ********" in out
    assert "Gemini API Key: ********" in out


def test_system_backup_execute(system_cmd, capsys):
    args = argparse.Namespace(verb="backup", output="test.zaf", user=False)

    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"),
        patch("zotero_cli.cli.commands.system_cmd.BackupService") as mock_backup_service_cls,
    ):
        mock_service = mock_backup_service_cls.return_value
        system_cmd.execute(args)

        mock_service.backup_system.assert_called_once_with("test.zaf")

    out, _ = capsys.readouterr()
    assert "Backup complete: test.zaf" in out


def test_system_normalize_bib(system_cmd, capsys):
    args = argparse.Namespace(verb="normalize", file="test.bib", output="out.csv")

    with (
        patch("zotero_cli.cli.commands.system_cmd.BibtexLibGateway") as mock_gw_cls,
        patch("zotero_cli.cli.commands.system_cmd.CanonicalCsvLibGateway") as mock_canon_cls,
    ):
        mock_gw = mock_gw_cls.return_value
        mock_gw.parse_file.return_value = iter([])
        mock_canon = mock_canon_cls.return_value

        system_cmd.execute(args)

        mock_gw.parse_file.assert_called_once_with("test.bib")
        mock_canon.write_file.assert_called_once()


def test_system_normalize_csv_springer(system_cmd, capsys):
    args = argparse.Namespace(verb="normalize", file="test.csv", output="out.csv")

    # Mock file content to trigger Springer detection
    m_open = mock_open(read_data="Item Title,DOI\nPaper 1,10.1/1")

    with (
        patch("builtins.open", m_open),
        patch("zotero_cli.cli.commands.system_cmd.SpringerCsvLibGateway") as mock_gw_cls,
        patch("zotero_cli.cli.commands.system_cmd.CanonicalCsvLibGateway"),
    ):
        mock_gw = mock_gw_cls.return_value
        mock_gw.parse_file.return_value = iter([])

        system_cmd.execute(args)

        mock_gw.parse_file.assert_called_once()


def test_system_normalize_csv_ieee(system_cmd, capsys):
    args = argparse.Namespace(verb="normalize", file="test.csv", output="out.csv")

    # Mock file content to trigger IEEE detection
    m_open = mock_open(read_data="Document Title,DOI\nPaper 1,10.1/1")

    with (
        patch("builtins.open", m_open),
        patch("zotero_cli.cli.commands.system_cmd.IeeeCsvLibGateway") as mock_gw_cls,
        patch("zotero_cli.cli.commands.system_cmd.CanonicalCsvLibGateway"),
    ):
        mock_gw = mock_gw_cls.return_value
        mock_gw.parse_file.return_value = iter([])

        system_cmd.execute(args)

        mock_gw.parse_file.assert_called_once()


def test_system_jobs_list(system_cmd, capsys):
    args = argparse.Namespace(verb="jobs", jobs_verb="list", type=None, limit=50)

    mock_job = MagicMock()
    mock_job.id = "1"
    mock_job.task_type = "test"
    mock_job.item_key = "K1"
    mock_job.status = "PENDING"
    mock_job.attempts = "0"
    mock_job.next_retry_at = None
    mock_job.last_error = None

    with patch("zotero_cli.infra.factory.GatewayFactory.get_job_queue_service") as mock_get_svc:
        mock_service = mock_get_svc.return_value
        mock_service.repo.list_jobs.return_value = [mock_job]

        system_cmd.execute(args)

    out, _ = capsys.readouterr()
    assert "Background System Jobs" in out
    assert "PENDING" in out
    assert "K1" in out


def test_system_jobs_retry(system_cmd, capsys):
    args = argparse.Namespace(verb="jobs", jobs_verb="retry", id=123)

    with patch("zotero_cli.infra.factory.GatewayFactory.get_job_queue_service") as mock_get_svc:
        mock_service = mock_get_svc.return_value
        mock_job = MagicMock()
        mock_service.repo.get_job.return_value = mock_job
        mock_service.repo.update_job.return_value = True

        system_cmd.execute(args)

        mock_service.repo.get_job.assert_called_with(123)
        assert mock_job.status == "PENDING"
        assert "Job 123 reset to PENDING" in capsys.readouterr().out


def test_system_jobs_run(system_cmd, capsys):
    args = argparse.Namespace(verb="jobs", jobs_verb="run", type="fetch_pdf", count=5, watch=False)

    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_job_queue_service"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_pdf_finder_service") as mock_get_finder,
        patch("zotero_cli.cli.commands.system_cmd.asyncio.run") as mock_run,
    ):
        mock_finder = mock_get_finder.return_value
        system_cmd.execute(args)

        mock_run.assert_called_once()
        mock_finder.process_jobs.assert_called_with(count=5)

    assert "Starting worker for task type 'fetch_pdf'" in capsys.readouterr().out


def test_system_groups(system_cmd, capsys):
    args = argparse.Namespace(verb="groups", user=False)
    with patch("zotero_cli.cli.commands.system_cmd.ListCommand") as mock_list_cmd_cls:
        mock_list_cmd = mock_list_cmd_cls.return_value
        system_cmd.execute(args)
        assert args.list_type == "groups"
        mock_list_cmd.execute.assert_called_once_with(args)


def test_system_switch(system_cmd, capsys):
    args = argparse.Namespace(verb="switch", query="MyGroup")
    with (
        patch("rich.prompt.Confirm.ask", return_value=True),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_get_gw,
        patch("zotero_cli.core.config.ConfigManager") as mock_cfg_mgr_cls,
        patch("zotero_cli.core.config.get_config") as mock_get_cfg,
    ):
        mock_config = MagicMock()
        mock_config.user_id = "123"
        mock_get_cfg.return_value = mock_config

        mock_gw = mock_get_gw.return_value
        mock_gw.get_user_groups.return_value = [{"id": "456", "data": {"name": "MyGroup"}}]
        mock_cfg_mgr = mock_cfg_mgr_cls.return_value

        system_cmd.execute(args)

        mock_cfg_mgr.save_group_context.assert_called_with("456")
        assert "Switched context to group: MyGroup (456)" in capsys.readouterr().out


def test_system_switch_no_matches(system_cmd, capsys):
    args = argparse.Namespace(verb="switch", query="NonExistent")
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_get_gw,
        patch("zotero_cli.core.config.get_config") as mock_get_cfg,
    ):
        mock_config = MagicMock()
        mock_config.user_id = "123"
        mock_get_cfg.return_value = mock_config
        mock_gw = mock_get_gw.return_value
        mock_gw.get_user_groups.return_value = []
        system_cmd.execute(args)
        assert "No groups found matching 'NonExistent'" in capsys.readouterr().out


def test_system_restore_placeholder(system_cmd, capsys):
    args = argparse.Namespace(verb="restore", file="test.zaf", dry_run=True)
    system_cmd.execute(args)
    assert "Restore functionality is pending implementation" in capsys.readouterr().out


def test_system_normalize_unsupported(system_cmd, capsys):
    args = argparse.Namespace(verb="normalize", file="test.txt", output="out.csv")
    system_cmd.execute(args)
    assert "Error: Unsupported file extension .txt" in capsys.readouterr().out


def test_system_jobs_run_watch(system_cmd, capsys):
    args = argparse.Namespace(verb="jobs", jobs_verb="run", type="fetch_pdf", watch=True)
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_job_queue_service") as mock_get_svc,
        patch("zotero_cli.infra.factory.GatewayFactory.get_pdf_finder_service"),
        patch("zotero_cli.cli.commands.system_cmd.asyncio.run"),
        patch("zotero_cli.cli.commands.system_cmd.time.sleep"),
        patch("rich.live.Live"),
    ):
        mock_service = mock_get_svc.return_value
        mock_job = MagicMock(status="PENDING")
        mock_job.id = "1"
        mock_job.item_key = "K1"
        mock_job.attempts = "0"
        mock_job.last_error = ""

        mock_service.repo.list_jobs.side_effect = [[mock_job], [mock_job], [mock_job], [], []]
        system_cmd.execute(args)
        assert mock_service.repo.list_jobs.call_count >= 2


def test_system_command_register_args(system_cmd):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    cmd_parser = subparsers.add_parser(system_cmd.name)
    system_cmd.register_args(cmd_parser)
    # Check that it added subparsers
    assert any(isinstance(a, argparse._SubParsersAction) for a in cmd_parser._actions)
