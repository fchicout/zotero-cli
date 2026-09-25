"""
Points HOME and the XDG/Windows config directories at a throwaway temp dir
for a test session (Issue #365).

zotero-cli keeps its config, logs, job queue, snowball graphs and vector
stores under the user's config directory, and code under test that resolves
default paths (`get_storage_dir()`, `ConfigManager()`, `setup_logging()`)
would otherwise write into the developer's real `~/.config/zotero-cli`. The
pre-push hook runs the unit suite on every `git push`, so that happened
silently for months.

Called at import time from the unit and docs conftests, before any
zotero_cli module is imported. The e2e suite deliberately keeps the real
environment: it talks to a live library with the developer's own config.
"""

import atexit
import os
import shutil
import tempfile
from pathlib import Path

_REAL_HOME = Path(os.path.expanduser("~"))


def isolate_home() -> Path:
    """Redirects home/config/data dirs to a new temp dir and returns it.
    Idempotent: a second call reuses the first directory."""
    existing = os.environ.get("ZOTERO_CLI_TEST_HOME")
    if existing:
        return Path(existing)

    # Keep downloaded model caches where they are (a test downloading a model
    # into a fresh temp dir on every run would be slow, not safer).
    os.environ.setdefault("HF_HOME", str(_REAL_HOME / ".cache" / "huggingface"))

    home = Path(tempfile.mkdtemp(prefix="zotero-cli-test-home-"))
    os.environ["ZOTERO_CLI_TEST_HOME"] = str(home)
    os.environ["HOME"] = str(home)
    os.environ["USERPROFILE"] = str(home)
    os.environ["XDG_CONFIG_HOME"] = str(home / ".config")
    os.environ["XDG_DATA_HOME"] = str(home / ".local" / "share")
    os.environ["XDG_STATE_HOME"] = str(home / ".local" / "state")
    os.environ["APPDATA"] = str(home / "AppData" / "Roaming")
    os.environ["LOCALAPPDATA"] = str(home / "AppData" / "Local")
    for env_key in ("ZOTERO_API_KEY", "ZOTERO_LIBRARY_ID", "ZOTERO_USER_ID"):
        os.environ.pop(env_key, None)
    atexit.register(shutil.rmtree, home, True)
    return home


def real_home() -> Path:
    """The developer's actual home directory, captured before isolation."""
    return _REAL_HOME
