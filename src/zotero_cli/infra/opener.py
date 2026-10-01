import logging

# subprocess: only used with fixed argv lists below, never shell=True
import os
import subprocess  # nosec B404
import sys
import webbrowser
from urllib.parse import urlparse

from zotero_cli.core.interfaces import OpenerService as IOpenerService
from zotero_cli.core.utils.notify import NotifyMixin, notify_or_log


def is_web_url(url: str) -> bool:
    """True for an absolute http(s) URL with a host, and nothing else."""
    if not url or any(ch in url for ch in "\r\n\t\\") or url != url.strip():
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


logger = logging.getLogger(__name__)


class OpenerService(IOpenerService, NotifyMixin):
    """
    Cross-platform file opener service.
    Implements 'Try-Then-Link' protocol:
    1. Try to open using native OS launcher.
    2. If fail (or headless), fallback to printing file:// link.
    """

    def open_file(self, path: str) -> bool:
        """
        Attempts to open the file at `path` using the default application.
        Returns True if the command was successfully dispatched.
        """
        if not os.path.exists(path):
            self._say(f"Error: File not found: {path}", logging.ERROR)
            return False

        try:
            if sys.platform == "win32":
                # OS-native opener, no shell involved
                os.startfile(path)  # type: ignore  # nosec B606
            elif sys.platform == "darwin":  # macOS
                # "open" resolved via PATH by design (cross-platform opener), fixed argv, no shell
                subprocess.run(["open", path], check=True)  # nosec B607, B603
            else:  # Linux/Unix
                # "xdg-open" resolved via PATH by design (cross-platform opener), fixed argv, no shell
                subprocess.run(["xdg-open", path], check=True)  # nosec B607, B603
            return True
        except Exception:
            # Fallback
            OpenerService.print_link(path)
            return False

    def open_url(self, url: str) -> bool:
        """
        Opens an http(s) URL in the default browser. Anything else is
        refused: item URLs are editable by anyone with write access to a
        shared library, and handing them to the OS launcher (os.startfile,
        xdg-open) would let a UNC path like \\\\host\\share\\x.exe connect
        out or run a program.
        """
        if not is_web_url(url):
            self._say("Refusing to open a non-http(s) URL.", logging.WARNING)
            return False
        try:
            return webbrowser.open(url)
        except webbrowser.Error:
            return False

    @staticmethod
    def print_link(path: str) -> None:
        """
        Prints a clickable file URL for terminal emulators that support it.
        """
        abs_path = os.path.abspath(path)
        # Handle Windows paths for file URI
        if os.name == "nt":
            abs_path = abs_path.replace("\\", "/")

        notify_or_log(
            None, logger, f"\n[Unable to open natively. Click to open]: file://{abs_path}\n"
        )
