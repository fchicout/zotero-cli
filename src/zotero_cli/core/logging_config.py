import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

_configured = False

_FILE_MAX_BYTES = 5 * 1024 * 1024
_FILE_BACKUP_COUNT = 3


def setup_logging(verbose: bool = False, log_dir: Optional[Path] = None) -> None:
    """
    Configure the root logger once per process (Issue #292).

    Without this, the codebase's disciplined `logger.info`/`.debug`/
    `.warning`/`.exception` calls are effectively write-only: Python's
    default root logger level is WARNING with no handler attached, so
    every `.info`/`.debug` call vanishes entirely, and `.warning`/
    `.exception` fall through to `logging.lastResort` - one unformatted
    line to stderr, no timestamp, no persistence. For a tool whose own
    docs describe long-running background jobs (`slr snowball discovery`,
    `system jobs`) meant to be revisited later, that left no way to debug
    a failed job from logs alone.

    Adds two handlers: a stderr stream (matching the pre-existing default
    visibility - WARNING+ - unless `verbose` requests DEBUG) and a
    rotating file under `get_storage_dir() / "logs" / "zotero-cli.log"`
    that always captures INFO+ regardless of verbosity, so unattended
    runs leave a durable trail even without `--verbose`.
    """
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG if verbose else logging.WARNING)
    stream_handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    root.addHandler(stream_handler)

    try:
        if log_dir is None:
            from zotero_cli.core.config import get_storage_dir

            log_dir = get_storage_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "zotero-cli.log",
            maxBytes=_FILE_MAX_BYTES,
            backupCount=_FILE_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root.addHandler(file_handler)
    except OSError as e:
        # A read-only/unwritable storage dir shouldn't block the CLI from
        # running at all - degrade to stderr-only logging, but still
        # surface why the file handler wasn't set up rather than swallowing
        # the failure silently.
        print(f"Warning: Could not set up log file at {log_dir}: {e}", file=sys.stderr)


def reset_logging_for_tests() -> None:
    """Test-only helper: undo setup_logging()'s handlers/idempotency guard
    so each test that exercises logging behavior starts from a clean
    root logger instead of silently no-op'ing on the second+ call."""
    global _configured
    _configured = False
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
