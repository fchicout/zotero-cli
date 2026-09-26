import io
import logging
import logging.handlers
import os
import re
import sys
from pathlib import Path
from typing import Optional, Set, cast

_configured = False

REDACTED = "[REDACTED]"

# Secret values seen at runtime (config keys, a key typed into `init`).
# Their literal text is masked anywhere it shows up in a log record.
_secrets: Set[str] = set()

# Credentials some APIs take in the URL (NCBI's api_key, Unpaywall's
# email, ...) - they end up in exception messages and HTTP debug logs.
_QUERY_SECRET_RE = re.compile(
    r"(?i)([?&](?:api_?key|key|token|access_token|email|password|secret)=)[^&\s#'\"]+"
)
# Zotero's GET /keys/<api_key> puts the key itself in the path.
_KEYS_PATH_RE = re.compile(r"(/keys/)(?!current\b)[^/?#\s'\"]+")
# Shorter values are too likely to match ordinary text.
_MIN_SECRET_LENGTH = 6

_FILE_MAX_BYTES = 5 * 1024 * 1024
_FILE_BACKUP_COUNT = 3


def register_secrets(*values: Optional[str]) -> None:
    """Adds values to mask in every log record from now on."""
    for value in values:
        if value and len(value) >= _MIN_SECRET_LENGTH:
            _secrets.add(value)


def redact(text: str) -> str:
    """Masks credentials in `text`: registered secret values, credential
    query parameters, and the key in a Zotero `/keys/<key>` path."""
    for secret in sorted(_secrets, key=len, reverse=True):
        text = text.replace(secret, REDACTED)
    text = _QUERY_SECRET_RE.sub(lambda m: m.group(1) + REDACTED, text)
    return _KEYS_PATH_RE.sub(lambda m: m.group(1) + REDACTED, text)


class RedactingFilter(logging.Filter):
    """Masks credentials in a record's message, traceback and stack before
    any handler formats it. Attached to both handlers, so the log file and
    stderr (what users paste into bug reports) never carry a key."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        if record.stack_info:
            record.stack_info = redact(record.stack_info)
        return True


class PrivateRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """A RotatingFileHandler whose files are created 0600. `_open` also
    runs on every rollover, so rotated files get the same mode."""

    def _open(self) -> io.TextIOWrapper:
        fd = os.open(self.baseFilename, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        if os.name != "nt":
            # os.open's mode only applies to a newly created file.
            os.chmod(self.baseFilename, 0o600)
        return cast(
            io.TextIOWrapper,
            os.fdopen(fd, self.mode, encoding=self.encoding, errors=self.errors),
        )


def _make_private_dir(path: Path) -> None:
    from zotero_cli.core.config import make_private_dir

    make_private_dir(path)


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
    # httpx logs every request URL (query string included) at INFO, which
    # the file handler would otherwise keep.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    redacting_filter = RedactingFilter()

    stream_handler = logging.StreamHandler()
    stream_handler.addFilter(redacting_filter)
    stream_handler.setLevel(logging.DEBUG if verbose else logging.WARNING)
    stream_handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    root.addHandler(stream_handler)

    try:
        if log_dir is None:
            from zotero_cli.core.config import default_storage_dir

            # This runs before anything else touches the storage directory,
            # which also holds config.toml, jobs.sqlite and vector stores,
            # so it's where the directory gets its 0700 mode. Logs always go
            # here, whichever --config is used.
            storage_dir = default_storage_dir()
            _make_private_dir(storage_dir)
            log_dir = storage_dir / "logs"
        _make_private_dir(log_dir)
        file_handler = PrivateRotatingFileHandler(
            log_dir / "zotero-cli.log",
            maxBytes=_FILE_MAX_BYTES,
            backupCount=_FILE_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.addFilter(redacting_filter)
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
    _secrets.clear()
    root = logging.getLogger()
    # A slice copy, not list(root.handlers) - removeHandler() mutates
    # root.handlers in place, so iterating the live list would skip every
    # other handler.
    for handler in root.handlers[:]:
        root.removeHandler(handler)
