"""How domain services say something to whoever called them (Issue #393).

A service must not write to the terminal. Its messages go to a `notify`
callable when there is one, and to the service's logger otherwise. The CLI
entry point installs a default sink that writes to stderr, so command output
is unchanged; code that embeds the services (no `main()`) gets plain logging.
A service can also be given its own `notify=` to override the default.
"""

import logging
from typing import Callable, Optional

Notify = Callable[[str], None]

_default_notify: Optional[Notify] = None


def set_default_notify(notify: Optional[Notify]) -> None:
    """Install (or clear, with None) the process-wide sink. Set once by the CLI."""
    global _default_notify
    _default_notify = notify


def notify_or_log(
    notify: Optional[Notify],
    log: logging.Logger,
    message: str,
    level: int = logging.INFO,
) -> None:
    sink = notify if notify is not None else _default_notify
    if sink is not None:
        sink(message)
    else:
        log.log(level, message)


class NotifyMixin:
    """`self._say(message, level)` for services; `notify` overrides the default sink."""

    notify: Optional[Notify] = None

    def _say(self, message: str, level: int = logging.INFO) -> None:
        notify_or_log(self.notify, logging.getLogger(type(self).__module__), message, level)
