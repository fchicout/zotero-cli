import logging
import logging.handlers

from zotero_cli.core import logging_config
from zotero_cli.core.logging_config import setup_logging


def test_setup_logging_adds_stderr_and_file_handlers(tmp_path):
    logging_config.reset_logging_for_tests()
    log_dir = tmp_path / "logs"

    setup_logging(verbose=False, log_dir=log_dir)

    root = logging.getLogger()
    assert len(root.handlers) == 2
    assert (log_dir / "zotero-cli.log").parent.exists()

    logging_config.reset_logging_for_tests()


def test_setup_logging_is_idempotent(tmp_path):
    """Regression test for Issue #292: called once per process - a second
    call (e.g. from a test harness invoking main() twice) must not stack
    duplicate handlers."""
    logging_config.reset_logging_for_tests()
    log_dir = tmp_path / "logs"

    setup_logging(verbose=False, log_dir=log_dir)
    setup_logging(verbose=True, log_dir=log_dir)

    root = logging.getLogger()
    assert len(root.handlers) == 2

    logging_config.reset_logging_for_tests()


def test_setup_logging_file_handler_captures_info_regardless_of_verbose(tmp_path):
    """Regression test for Issue #292: the file handler must always
    capture INFO+ so background job failures leave a durable trail even
    without --verbose - only the stderr handler's level should depend on
    it."""
    logging_config.reset_logging_for_tests()
    log_dir = tmp_path / "logs"

    setup_logging(verbose=False, log_dir=log_dir)

    root = logging.getLogger()
    stream_handler = next(h for h in root.handlers if isinstance(h, logging.StreamHandler))
    file_handler = next(
        h for h in root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)
    )
    assert stream_handler.level == logging.WARNING
    assert file_handler.level == logging.INFO

    logger = logging.getLogger("zotero_cli.test")
    logger.info("hello from a background job")
    for h in root.handlers:
        h.flush()

    log_file = log_dir / "zotero-cli.log"
    assert log_file.exists()
    assert "hello from a background job" in log_file.read_text()

    logging_config.reset_logging_for_tests()


def test_setup_logging_verbose_lowers_stderr_level(tmp_path):
    logging_config.reset_logging_for_tests()
    log_dir = tmp_path / "logs"

    setup_logging(verbose=True, log_dir=log_dir)

    root = logging.getLogger()
    stream_handler = next(h for h in root.handlers if isinstance(h, logging.StreamHandler))
    assert stream_handler.level == logging.DEBUG

    logging_config.reset_logging_for_tests()


def test_setup_logging_degrades_gracefully_on_unwritable_log_dir(tmp_path, monkeypatch, capsys):
    """A read-only/unwritable storage dir must not prevent the CLI from
    running - only the file handler should be skipped, and the failure
    must be surfaced (not silently swallowed)."""
    logging_config.reset_logging_for_tests()
    log_dir = tmp_path / "logs"

    def raise_oserror(*args, **kwargs):
        raise OSError("Permission denied")

    monkeypatch.setattr("pathlib.Path.mkdir", raise_oserror)

    setup_logging(verbose=False, log_dir=log_dir)

    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0], logging.StreamHandler)
    assert "Permission denied" in capsys.readouterr().err

    logging_config.reset_logging_for_tests()
