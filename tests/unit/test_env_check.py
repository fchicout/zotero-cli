from unittest.mock import MagicMock, patch

import pytest

# Note: We import inside tests to control when the top-level code in main.py executes
# or we use the function directly if possible.


def test_verify_environment_valid():
    from zotero_cli.cli.main import verify_environment

    with patch("sys.version_info", (3, 11, 5)):
        # Should not raise SystemExit
        verify_environment()


def test_verify_environment_invalid():
    from zotero_cli.cli.main import verify_environment

    with patch("sys.version_info", (3, 10, 0)):
        with patch("sys.exit") as mock_exit:
            verify_environment()
            mock_exit.assert_called_once_with(1)


@pytest.mark.parametrize("version", [(3, 11, 0), (3, 11, 4)])
def test_verify_environment_rejects_python_before_3_11_5(version):
    """Issue #646: the fixed soupsieve releases need 3.11.5."""
    from zotero_cli.cli.main import verify_environment

    with patch("sys.version_info", version):
        with patch("sys.exit") as mock_exit:
            verify_environment()
            mock_exit.assert_called_once_with(1)


def test_verify_environment_invalid_rich_available(capsys):
    from zotero_cli.cli.main import verify_environment

    with patch("sys.version_info", (3, 10, 0)):
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

    with patch("sys.version_info", (3, 10, 0)):
        with patch("sys.exit"):
            # Force ImportError for rich
            with patch("builtins.__import__", side_effect=ImportError("No module named 'rich'")):
                verify_environment()
                captured = capsys.readouterr()
                assert "Incompatible Environment Detected" in captured.err
