class ZoteroCliError(Exception):
    """Base exception for Zotero CLI."""

    pass


class ConfigurationError(ZoteroCliError):
    """
    Raised when the active ZoteroConfig can't resolve to a usable gateway
    (missing credentials, unparseable group URL, no target library). Caught
    at the CLI boundary (cli/main.py) to print a clean message and exit 1,
    instead of infra code calling sys.exit directly.
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
