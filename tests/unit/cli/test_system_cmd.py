import argparse
from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.cli.commands.system_cmd import SystemCommand


@pytest.fixture
def system_cmd():
    return SystemCommand()


def test_system_info(system_cmd, capsys):
    with patch("zotero_cli.core.config.get_config") as mock_get_config:
        mock_config = MagicMock()
        mock_config.library_id = "123"
        mock_config.library_type = "user"
        mock_config.api_key = "key"
        mock_config.target_group_url = None
        mock_get_config.return_value = mock_config

        args = argparse.Namespace(verb="info", config=None)
        system_cmd.execute(args)

        out = capsys.readouterr().out
        assert "Library ID:  123" in out
        assert "Library Type: user" in out


def test_system_verify_success(system_cmd, capsys):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_verify_service") as mock_get_service:
        mock_service = mock_get_service.return_value
        mock_report = MagicMock()
        mock_report.is_valid = True
        mock_report.item_count = 10
        mock_report.file_count = 5
        mock_report.manifest = {"timestamp": "2024-01-01"}
        mock_service.verify_archive.return_value = mock_report

        args = argparse.Namespace(verb="verify", file="test.zaf")
        system_cmd.execute(args)

        out = capsys.readouterr().out
        assert "✅ ARCHIVE IS VALID" in out
        assert "Items: 10" in out


def test_system_verify_failure(system_cmd, capsys):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_verify_service") as mock_get_service:
        mock_service = mock_get_service.return_value
        mock_report = MagicMock()
        mock_report.is_valid = False
        mock_report.errors = ["Missing manifest.json"]
        mock_service.verify_archive.return_value = mock_report

        args = argparse.Namespace(verb="verify", file="bad.zaf")
        system_cmd.execute(args)

        out = capsys.readouterr().out
        assert "❌ ARCHIVE IS INVALID OR CORRUPT" in out
        assert "Missing manifest.json" in out


def test_system_backup(system_cmd, capsys):
    with patch("zotero_cli.core.services.backup_service.BackupService.backup_system") as mock_backup:
        args = argparse.Namespace(verb="backup", output="test.zaf", user=False)
        system_cmd.execute(args)
        
        out = capsys.readouterr().out
        assert "Starting System Backup to test.zaf" in out
        assert "Backup complete: test.zaf" in out
        mock_backup.assert_called_once()

def test_system_switch(system_cmd, capsys):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_gw_factory, \
         patch("rich.prompt.Confirm.ask", return_value=True), \
         patch("zotero_cli.core.config.ConfigManager.save_group_context") as mock_save:
        
        mock_gw = mock_gw_factory.return_value
        mock_gw.get_user_groups.return_value = [
            {"id": 123, "data": {"name": "Test Group"}}
        ]
        
        args = argparse.Namespace(verb="switch", query="Test", user=False)
        system_cmd.execute(args)
        
        out = capsys.readouterr().out
        assert "Switched context to group: Test Group (123)" in out
        mock_save.assert_called_with("123")

def test_system_normalize(system_cmd, capsys, tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("title,doi\nPaper 1,10.1/1", encoding="utf-8")
    output_file = tmp_path / "canon.csv"
    
    with patch("zotero_cli.core.strategies.CanonicalCsvImportStrategy.fetch_papers") as mock_fetch, \
         patch("zotero_cli.infra.canonical_csv_lib.CanonicalCsvLibGateway.write_file") as mock_write:
        
        mock_fetch.return_value = iter([])
        
        args = argparse.Namespace(verb="normalize", file=str(csv_file), output=str(output_file))
        system_cmd.execute(args)
        
        out = capsys.readouterr().out
        assert "Normalization complete" in out


def test_system_restore_dry_run(system_cmd, capsys):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_restore_service") as mock_get_service:
        mock_service = mock_get_service.return_value
        mock_report = MagicMock()
        mock_report.errors = []
        mock_report.collections_created = 1
        mock_report.items_created = 2
        mock_report.items_skipped_existing = 3
        mock_report.attachments_uploaded = 4
        mock_service.restore_archive.return_value = mock_report

        args = argparse.Namespace(verb="restore", file="test.zaf", dry_run=True, user=False)
        system_cmd.execute(args)

        out = capsys.readouterr().out
        assert "Restoring from archive: test.zaf" in out
        assert "DRY RUN" in out
        assert "Restore Plan Summary" in out
        assert "Collections Created" in out
        assert "1" in out
        assert "RESTORE SIMULATED" in out


def test_system_groups(system_cmd, capsys):
    with patch("zotero_cli.core.config.get_config") as mock_get_config, \
         patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_gw_factory:
        
        mock_config = MagicMock()
        mock_config.user_id = "12345"
        mock_get_config.return_value = mock_config
        
        mock_gw = mock_gw_factory.return_value
        mock_gw.get_user_groups.return_value = [
            {"id": 123, "data": {"name": "Lab A"}}
        ]
        
        args = argparse.Namespace(verb="groups", user=False)
        system_cmd.execute(args)
        
        out = capsys.readouterr().out
        assert "Zotero Groups" in out
        assert "Lab A" in out

def test_system_jobs_list(system_cmd, capsys):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_job_queue_service") as mock_job_factory:
        mock_job_service = mock_job_factory.return_value
        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.task_type = "fetch"
        mock_job.status = "PENDING"
        mock_job.item_key = "K1"
        mock_job.attempts = 0
        mock_job.next_retry_at = None
        mock_job.last_error = None
        
        mock_job_service.repo.list_jobs.return_value = [mock_job]
        
        args = argparse.Namespace(verb="jobs", jobs_verb="list", type=None, limit=50)
        system_cmd.execute(args)
        
        out = capsys.readouterr().out
        assert "Background System Jobs" in out
        assert "fetch" in out

def test_system_jobs_retry(system_cmd, capsys):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_job_queue_service") as mock_job_factory:
        mock_job_service = mock_job_factory.return_value
        mock_job = MagicMock()
        mock_job.id = 123
        mock_job_service.repo.get_job.return_value = mock_job
        mock_job_service.repo.update_job.return_value = True
        
        args = argparse.Namespace(verb="jobs", jobs_verb="retry", id=123)
        system_cmd.execute(args)
        
        out = capsys.readouterr().out
        assert "Job 123 reset to PENDING" in out

def test_system_jobs_run(system_cmd, capsys):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_job_queue_service"), \
         patch("zotero_cli.infra.factory.GatewayFactory.get_pdf_finder_service") as mock_worker_factory, \
         patch("asyncio.run") as mock_run:
        
        mock_worker = mock_worker_factory.return_value
        
        args = argparse.Namespace(verb="jobs", jobs_verb="run", type="fetch_pdf", count=10, watch=False)
        system_cmd.execute(args)
        
        out = capsys.readouterr().out
        assert "Starting worker for task type 'fetch_pdf'" in out
        assert "Done." in out
        mock_run.assert_called_once()

def test_system_switch_ambiguous(system_cmd, capsys):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_gw_factory:
        mock_gw = mock_gw_factory.return_value
        mock_gw.get_user_groups.return_value = [
            {"id": 1, "data": {"name": "Lab A"}},
            {"id": 2, "data": {"name": "Lab B"}}
        ]
        
        args = argparse.Namespace(verb="switch", query="Lab", user=False)
        system_cmd.execute(args)
        
        out = capsys.readouterr().out
        assert "Multiple groups found" in out

def test_system_restore_failure(system_cmd, capsys):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_restore_service") as mock_get_service:
        mock_service = mock_get_service.return_value
        mock_report = MagicMock()
        mock_report.errors = ["Some error"]
        mock_report.collections_created = 0
        mock_report.items_created = 0
        mock_report.items_skipped_existing = 0
        mock_report.attachments_uploaded = 0
        mock_service.restore_archive.return_value = mock_report

        args = argparse.Namespace(verb="restore", file="bad.zaf", dry_run=False, user=False)
        system_cmd.execute(args)

        out = capsys.readouterr().out
        assert "Restore encountered errors" in out
        assert "Some error" in out

def test_system_jobs_watch(system_cmd, capsys):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_job_queue_service") as mock_job_factory, \
         patch("zotero_cli.infra.factory.GatewayFactory.get_pdf_finder_service"), \
         patch("asyncio.run"), \
         patch("time.sleep"):
        
        mock_job_service = mock_job_factory.return_value
        
        # Create a mock job with real strings for rich to render
        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.item_key = "K1"
        mock_job.status = "PENDING"
        mock_job.attempts = 0
        mock_job.last_error = ""
        
        # Return pending job once, then empty for all subsequent calls
        def list_jobs_side_effect(*args, **kwargs):
            if not hasattr(list_jobs_side_effect, "called"):
                list_jobs_side_effect.called = True
                return [mock_job]
            return []
            
        mock_job_service.repo.list_jobs.side_effect = list_jobs_side_effect
        
        args = argparse.Namespace(verb="jobs", jobs_verb="run", type="fetch_pdf", count=None, watch=True)
        system_cmd.execute(args)
        assert True
