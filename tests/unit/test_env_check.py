from unittest.mock import MagicMock, patch

# Note: We import inside tests to control when the top-level code in main.py executes
# or we use the function directly if possible.


def test_verify_environment_valid():
    from zotero_cli.cli.main import verify_environment

    with patch("sys.version_info", (3, 10, 0)):
        # Should not raise SystemExit
        verify_environment()


def test_verify_environment_invalid():
    from zotero_cli.cli.main import verify_environment

    with patch("sys.version_info", (3, 9, 0)):
        with patch("sys.exit") as mock_exit:
            verify_environment()
            mock_exit.assert_called_once_with(1)


def test_verify_environment_invalid_rich_available(capsys):
    from zotero_cli.cli.main import verify_environment

    with patch("sys.version_info", (3, 9, 0)):
        with patch("sys.exit"):
            # Mock rich to ensure it's used
            mock_console = MagicMock()
            with patch("rich.console.Console", return_value=mock_console):
                # We need to mock Panel as well because it's imported
                with patch("rich.panel.Panel"):
                    verify_environment()
                    assert mock_console.print.called


def test_verify_environment_invalid_rich_unavailable(capsys):
    from zotero_cli.cli.main import verify_environment

    with patch("sys.version_info", (3, 9, 0)):
        with patch("sys.exit"):
            # Force ImportError for rich
            with patch("builtins.__import__", side_effect=ImportError("No module named 'rich'")):
                verify_environment()
                captured = capsys.readouterr()
                assert "Incompatible Environment Detected" in captured.err
