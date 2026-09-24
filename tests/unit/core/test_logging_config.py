import logging
import logging.handlers
import os

import pytest

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


def _read_log(log_dir):
    for handler in logging.getLogger().handlers:
        handler.flush()
    return (log_dir / "zotero-cli.log").read_text(encoding="utf-8")


def test_registered_secret_is_masked_in_log_file_and_traceback(tmp_path):
    logging_config.reset_logging_for_tests()
    log_dir = tmp_path / "logs"
    setup_logging(verbose=False, log_dir=log_dir)
    logging_config.register_secrets("s3cr3t-api-key-value")

    log = logging.getLogger("zotero_cli.test")
    log.warning("using key %s", "s3cr3t-api-key-value")
    try:
        raise RuntimeError("request failed for key s3cr3t-api-key-value")
    except RuntimeError:
        log.exception("lookup failed")

    content = _read_log(log_dir)
    assert "s3cr3t-api-key-value" not in content
    assert content.count("[REDACTED]") >= 2
    logging_config.reset_logging_for_tests()


def test_credentials_in_urls_are_masked_even_if_never_registered(tmp_path):
    """NCBI's api_key and Unpaywall's email travel as query parameters and
    Zotero's /keys/<key> puts the key in the path - all end up in
    exception messages (e.g. requests' HTTPError, tenacity retries)."""
    logging_config.reset_logging_for_tests()
    log_dir = tmp_path / "logs"
    setup_logging(verbose=False, log_dir=log_dir)

    log = logging.getLogger("zotero_cli.test")
    log.error(
        "500 for url: https://eutils.ncbi.nlm.nih.gov/efetch.fcgi?db=pubmed&api_key=NCBIKEY123&id=1"
    )
    log.error("GET https://api.unpaywall.org/v2/10.1/x?email=someone@example.org failed")
    log.error("403 for url: https://api.zotero.org/keys/ZOTEROKEY123456")

    content = _read_log(log_dir)
    for leaked in ("NCBIKEY123", "someone@example.org", "ZOTEROKEY123456"):
        assert leaked not in content
    assert "db=pubmed" in content and "id=1" in content
    assert "/keys/[REDACTED]" in content
    logging_config.reset_logging_for_tests()


def test_redact_keeps_keys_current_and_short_values():
    logging_config.reset_logging_for_tests()
    logging_config.register_secrets("abc", None, "")
    text = "GET https://api.zotero.org/keys/current - abc"
    assert logging_config.redact(text) == text
    logging_config.reset_logging_for_tests()


def test_httpx_request_logging_is_quieted(tmp_path):
    logging_config.reset_logging_for_tests()
    setup_logging(verbose=True, log_dir=tmp_path / "logs")
    assert logging.getLogger("httpx").getEffectiveLevel() == logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() == logging.WARNING
    logging_config.reset_logging_for_tests()


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_log_dir_and_file_are_private_even_if_dir_existed(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir(mode=0o755)
    os.chmod(log_dir, 0o755)
    (log_dir / "zotero-cli.log").write_text("old\n")
    os.chmod(log_dir / "zotero-cli.log", 0o644)

    logging_config.reset_logging_for_tests()
    setup_logging(verbose=False, log_dir=log_dir)
    logging.getLogger("zotero_cli.test").warning("hello")
    _read_log(log_dir)

    assert os.stat(log_dir).st_mode & 0o777 == 0o700
    assert os.stat(log_dir / "zotero-cli.log").st_mode & 0o777 == 0o600
    logging_config.reset_logging_for_tests()
