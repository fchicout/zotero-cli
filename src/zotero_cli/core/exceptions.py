# What each exit status means; the help epilog, `schema` and docs/EXIT_CODES.md all
# follow this (a test keeps the document in step).
EXIT_CODES = {
    0: "success",
    1: "error",
    2: "usage error",
    3: "not found",
    4: "authentication",
    5: "unavailable",
    6: "conflict",
    7: "partial failure",
    130: "interrupted",
}


class ZoteroCliError(Exception):
    """
    Base exception for zotero-cli. `main()` prints its message as one line
    on stderr and exits with `exit_code` (Issues #368, #370); the traceback
    only appears with `-v`. See docs/EXIT_CODES.md.
    """

    exit_code = 1


class UsageError(ZoteroCliError):
    """The command was called in a way it can't run (exit 2, like argparse)."""

    exit_code = 2


class NotFound(ZoteroCliError):
    """A key, collection or file the user named doesn't exist (exit 3)."""

    exit_code = 3


class AuthError(ZoteroCliError):
    """The API key was rejected or lacks access (exit 4)."""

    exit_code = 4


class Unavailable(ZoteroCliError):
    """The network or the service failed after retries (exit 5)."""

    exit_code = 5


class Conflict(ZoteroCliError):
    """The object changed since the version the command acted on (exit 6)."""

    exit_code = 6


class PartialFailure(ZoteroCliError):
    """Part of a batch failed; the rest was applied (exit 7)."""

    exit_code = 7


class ConfigurationError(ZoteroCliError):
    """
    Raised when the active ZoteroConfig can't resolve to a usable gateway
    (missing credentials, unparseable group URL, no target library). Caught
    at the CLI boundary (cli/main.py) to print a clean message and exit 1,
    instead of infra code calling sys.exit directly.
    """

    pass


class OfflineReadOnly(ConfigurationError):
    """A write was attempted in --offline mode, which is read-only apart from
    `item trash`/`item restore` (Issue #370). Exit 1."""

    def __init__(self, message: str = "Offline mode is read-only") -> None:
        super().__init__(f"{message}. Run the command without --offline to change your library.")


class AmbiguousCollectionError(UsageError):
    """
    Raised when a collection name matches more than one collection
    (Issue #381). Commands must not guess which one was meant, least of all
    destructive ones, so the user is asked to pass one of the listed keys.
    """

    def __init__(self, name: str, candidates: "list[tuple[str, str]]"):
        self.name = name
        self.candidates = candidates
        listing = "\n".join(f"  {key}  {path}" for key, path in candidates)
        super().__init__(
            f"Collection name '{name}' matches {len(candidates)} collections; "
            f"pass the key of the one you mean:\n{listing}"
        )


class ImportParseError(ZoteroCliError):
    """An input file for `import` couldn't be parsed (Issue #368: parse
    errors used to be printed while the import "succeeded" with 0 items)."""

    pass


class DataFileError(ZoteroCliError):
    """
    Raised when a file zotero-cli keeps its own state in can't be read.
    The file is set aside rather than replaced by an empty one, and the
    command stops (Issue #410); `main()` prints the message and exits 1.
    """

    pass


class RetryableError(ZoteroCliError):
    """
    Raised when an operation failed but should be retried later.
    Captured by JobQueue for rescheduling.
    """

    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after
