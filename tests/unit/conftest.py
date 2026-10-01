from unittest.mock import MagicMock

from tests.home_isolation import isolate_home
from tests.network_guard import ExternalConnectionGuard, offline_env

# Before any zotero_cli import: nothing in the unit suite may resolve the
# developer's real ~/.config/zotero-cli (Issue #365), or reach Hugging Face
# (Issue #389: huggingface_hub reads this variable once, at import).
isolate_home()
offline_env()

import pytest  # noqa: E402

from zotero_cli.core.config import ZoteroConfig  # noqa: E402


@pytest.fixture(autouse=True)
def _no_external_network(monkeypatch):
    """tests/unit never leaves this machine (Issue #389). A refused connection
    is also recorded, because code under test often catches Exception and
    would hide it: the test fails at teardown if any was attempted."""
    guard = ExternalConnectionGuard()
    guard.install(monkeypatch)
    yield guard
    assert not guard.attempts, f"unit test tried to reach the network: {guard.attempts}"


@pytest.fixture(autouse=True)
def _no_leaked_notify_sink():
    """`cli.main.main()` installs the stderr sink for domain services (Issue #393);
    clear it around every test so one test driving `main()` can't turn the next
    test's logging into terminal output."""
    from zotero_cli.core.utils.notify import set_default_notify

    set_default_notify(None)
    yield
    set_default_notify(None)


@pytest.fixture(autouse=True)
def _no_real_logging_setup(monkeypatch):
    """
    tests/unit must stay fully offline/file-write-free (CLAUDE.md) -
    `cli.main.main()` unconditionally calls `setup_logging()` at startup
    (Issue #292), which by default creates a rotating file handler under
    the real `get_storage_dir() / "logs"`. Any test that drives `main()`
    (most of `tests/test_cli.py`) would otherwise silently write a real
    `zotero-cli.log` to the developer's actual `~/.config/zotero-cli/`
    directory. Patched at the `cli.main` binding site specifically (a
    module-local `from ... import setup_logging` name, not the defining
    module's attribute) so it actually intercepts what `main()` calls.
    Also resets `logging_config`'s own idempotency guard/handlers around
    each test, so a test that explicitly wants to exercise
    `setup_logging()` itself starts from a clean, unconfigured root
    logger rather than a state some other test left behind.
    """
    from zotero_cli.core import logging_config

    logging_config.reset_logging_for_tests()
    monkeypatch.setattr("zotero_cli.cli.main.setup_logging", MagicMock())
    yield
    logging_config.reset_logging_for_tests()


@pytest.fixture
def mock_config() -> ZoteroConfig:
    """
    A minimal, valid ZoteroConfig for tests that just need *a* config to
    pass to a factory/service under test - not for tests exercising
    ZoteroConfig's own field-resolution logic itself (see
    test_config.py), which needs specific, deliberately-varied field
    combinations per case and shouldn't be forced through a shared
    default (Issue #254).

    ZoteroConfig is a frozen dataclass - override specific fields with
    `dataclasses.replace(mock_config, field=value)` rather than
    reconstructing one from scratch.
    """
    return ZoteroConfig(
        api_key="test_key",
        library_id="123",
        library_type="user",
        database_path="test.sqlite",
    )
