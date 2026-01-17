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
        mock_config.target_group_url = None
        mock_get_config.return_value = mock_config

        info_cmd.execute(args)

    out, _ = capsys.readouterr()
    assert "Library ID:  123" in out
    assert "Library Type: user" in out


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
