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


class AmbiguousCollectionError(ZoteroCliError):
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


class RetryableError(ZoteroCliError):
    """
    Raised when an operation failed but should be retried later.
    Captured by JobQueue for rescheduling.
    """

    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after
