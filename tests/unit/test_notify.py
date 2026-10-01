"""Domain services report through `notify` or the logger, never print (Issue #393)."""

import logging
from unittest.mock import MagicMock

from zotero_cli.cli.notify import stderr_notify
from zotero_cli.core.services.storage_service import StorageService
from zotero_cli.core.services.sync_service import SyncService
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


def _sync(notify=None):
    collections = MagicMock()
    collections.get_collection_id_by_name.return_value = None
    return SyncService(collections, MagicMock(), notify=notify)


def test_sync_service_reports_a_missing_collection_to_the_sink(capsys):
    sink = MagicMock()
    assert _sync(sink).recover_state_from_notes("Nope", "out.csv") is False
    sink.assert_called_once_with("Error: Collection 'Nope' not found.")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_sync_service_logs_when_nobody_listens(capsys, caplog):
    with caplog.at_level(logging.INFO):
        assert _sync().recover_state_from_notes("Nope", "out.csv") is False
    assert "Collection 'Nope' not found" in caplog.text
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


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


def test_a_default_sink_receives_service_messages_and_logging_stays_quiet(caplog):
    from zotero_cli.core.utils.notify import set_default_notify

    messages: list[str] = []
    set_default_notify(messages.append)
    with caplog.at_level(logging.DEBUG):
        assert _sync().recover_state_from_notes("Nope", "out.csv") is False
    assert messages == ["Error: Collection 'Nope' not found."]
    assert caplog.records == []


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
