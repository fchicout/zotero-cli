"""
Process-wide runtime options set once by the CLI entry point.

`--offline` used to live in a module global of `zotero_cli.cli.main`, read
back with `from zotero_cli.cli.main import OFFLINE_MODE`. When main.py runs
as `__main__` (the PyInstaller binaries, `python -m`), that import loads a
second copy of the module where the flag is still False, so every
`--offline` command went to the Web API (Issue #363). Keeping the flag
here, in a module that is never the entry point, avoids that.
"""

_offline = False


def set_offline_mode(offline: bool) -> None:
    global _offline
    _offline = bool(offline)


def is_offline_mode() -> bool:
    return _offline
