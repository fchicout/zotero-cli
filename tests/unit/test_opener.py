from unittest.mock import patch

import pytest

from zotero_cli.infra.opener import OpenerService


@pytest.fixture
def opener():
    return OpenerService()


@pytest.fixture
def mock_platform():
    with patch("platform.system") as m:
        yield m


@pytest.fixture
def mock_subprocess():
    with patch("subprocess.run") as m:
        yield m


@pytest.fixture
def mock_os_exists():
    with patch("os.path.exists") as m:
        yield m


def test_open_file_not_found(opener, mock_os_exists):
    mock_os_exists.return_value = False
    assert opener.open_file("non_existent.txt") is False


@patch("os.startfile", create=True)
def test_open_file_windows(mock_startfile, opener, mock_os_exists):
    mock_os_exists.return_value = True
    with patch("sys.platform", "win32"):
        assert opener.open_file("test.pdf") is True
        mock_startfile.assert_called_once_with("test.pdf")


def test_open_file_macos(mock_subprocess, opener, mock_os_exists):
    mock_os_exists.return_value = True
    with patch("sys.platform", "darwin"):
        assert opener.open_file("test.pdf") is True
        mock_subprocess.assert_called_once_with(["open", "test.pdf"], check=True)


def test_open_file_linux(mock_subprocess, opener, mock_os_exists):
    mock_os_exists.return_value = True
    with patch("sys.platform", "linux"):
        assert opener.open_file("test.pdf") is True
        mock_subprocess.assert_called_once_with(["xdg-open", "test.pdf"], check=True)


def test_open_file_failure_fallback(mock_subprocess, opener, mock_os_exists):
    mock_os_exists.return_value = True
    with patch("sys.platform", "linux"):
        mock_subprocess.side_effect = Exception("Fail")

        with patch("zotero_cli.infra.opener.OpenerService.print_link") as mock_print:
            assert opener.open_file("test.pdf") is False
            mock_print.assert_called_once_with("test.pdf")


def test_print_link(capsys, opener):
    opener.print_link("test.pdf")
    captured = capsys.readouterr()
    assert "file://" in captured.out
    assert "test.pdf" in captured.out


@pytest.mark.parametrize(
    "url",
    [
        r"\\attacker\share\paper.pdf.exe",
        "file:///etc/passwd",
        "paper.pdf",
        "javascript:alert(1)",
        "http://",
        " http://example.com",
        "http://example.com/\nsecond-line",
    ],
)
def test_open_url_refuses_non_web_urls(opener, url):
    with patch("webbrowser.open") as browser, patch("subprocess.run") as run:
        assert opener.open_url(url) is False
    browser.assert_not_called()
    run.assert_not_called()


def test_open_url_uses_the_browser_not_the_os_launcher(opener):
    with (
        patch("webbrowser.open", return_value=True) as browser,
        patch("subprocess.run") as run,
        patch("os.startfile", create=True) as startfile,
    ):
        assert opener.open_url("https://doi.org/10.1000/1") is True
    browser.assert_called_once_with("https://doi.org/10.1000/1")
    run.assert_not_called()
    startfile.assert_not_called()
