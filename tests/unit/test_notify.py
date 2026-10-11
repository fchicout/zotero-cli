"""Domain services report through `notify` or the logger, never print (Issue #393)."""

import logging
from unittest.mock import MagicMock

from zotero_cli.cli.notify import stderr_notify
from zotero_cli.core.services.storage_service import StorageService
from zotero_cli.core.utils.notify import notify_or_log


def test_notify_or_log_prefers_the_sink(caplog):
    sink = MagicMock()
    with caplog.at_level(logging.DEBUG):
        notify_or_log(sink, logging.getLogger("t"), "hello", logging.ERROR)
    sink.assert_called_once_with("hello")
    assert caplog.records == []


def test_notify_or_log_logs_at_the_given_level_without_a_sink(caplog):
    with caplog.at_level(logging.DEBUG):
        notify_or_log(None, logging.getLogger("t"), "careful", logging.WARNING)
    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [(logging.WARNING, "careful")]


def test_stderr_notify_writes_the_message_unchanged_to_stderr(capsys):
    stderr_notify("  Moved to /x")
    captured = capsys.readouterr()
    assert captured.err == "  Moved to /x\n"
    assert captured.out == ""


def test_storage_service_dry_run_lists_through_the_sink(tmp_path, capsys):
    gateway = MagicMock()
    config = MagicMock()
    config.storage_path = str(tmp_path / "store")
    config.resolve_library_target.return_value = ("1", "user")
    gateway.search_items.return_value = iter([])
    messages: list[str] = []
    service = StorageService(config, gateway, notify=messages.append)

    service.checkout_items(limit=5, dry_run=True)

    assert messages[0] == "Scanning for stored attachments (Limit: 5)..."
    assert capsys.readouterr().err == ""


def test_main_installs_the_stderr_sink(monkeypatch, capsys):
    """The CLI keeps showing what the services used to print themselves."""
    import sys

    from zotero_cli.cli.main import main
    from zotero_cli.core.utils import notify

    monkeypatch.setattr(sys, "argv", ["zotero-cli", "--help"])
    try:
        main()
    except SystemExit:
        pass
    assert notify._default_notify is stderr_notify
    capsys.readouterr()
