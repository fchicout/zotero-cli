"""How domain services say something to whoever called them (Issue #393).

A service must not write to the terminal. It takes an optional `notify`
callable: when the caller passes one (the CLI passes a function that writes
to stderr) the message goes there unchanged, and the caller owns the
presentation. Without one it goes to the service's logger at the given level.
"""

import logging
from typing import Callable, Optional

Notify = Callable[[str], None]


def notify_or_log(
    notify: Optional[Notify],
    log: logging.Logger,
    message: str,
    level: int = logging.INFO,
) -> None:
    if notify is not None:
        notify(message)
    else:
        log.log(level, message)
