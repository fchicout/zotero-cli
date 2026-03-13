class ZoteroCliError(Exception):
    """Base exception for Zotero CLI."""

    pass


class RetryableError(ZoteroCliError):
    """
    Raised when an operation failed but should be retried later.
    Captured by JobQueue for rescheduling.
    """

    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after
