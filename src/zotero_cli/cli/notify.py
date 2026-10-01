"""The terminal sink handed to domain services as `notify` (Issue #393)."""

import sys


def stderr_notify(message: str) -> None:
    print(message, file=sys.stderr)
