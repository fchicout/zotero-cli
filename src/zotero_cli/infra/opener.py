# subprocess: only used with fixed argv lists below, never shell=True
import os
import subprocess  # nosec B404
import sys

from zotero_cli.core.interfaces import OpenerService as IOpenerService


class OpenerService(IOpenerService):
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
            print(f"Error: File not found: {path}", file=sys.stderr)
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

    @staticmethod
    def print_link(path: str):
        """
        Prints a clickable file URL for terminal emulators that support it.
        """
        abs_path = os.path.abspath(path)
        # Handle Windows paths for file URI
        if os.name == "nt":
            abs_path = abs_path.replace("\\", "/")

        print(f"\n[Unable to open natively. Click to open]: file://{abs_path}\n")
