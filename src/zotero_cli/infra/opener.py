import os
import subprocess
import sys
import platform
from typing import Optional

class OpenerService:
    """
    Cross-platform file opener service.
    Implements 'Try-Then-Link' protocol:
    1. Try to open using native OS launcher.
    2. If fail (or headless), fallback to printing file:// link.
    """

    @staticmethod
    def open_file(path: str) -> bool:
        """
        Attempts to open the file at `path` using the default application.
        Returns True if the command was successfully dispatched.
        """
        if not os.path.exists(path):
            print(f"Error: File not found: {path}", file=sys.stderr)
            return False

        system_platform = platform.system()
        
        try:
            if system_platform == "Windows":
                os.startfile(path)
            elif system_platform == "Darwin":  # macOS
                subprocess.run(["open", path], check=True)
            else:  # Linux/Unix
                # Check for xdg-open or similar
                subprocess.run(["xdg-open", path], check=True)
            return True
        except Exception as e:
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
        if os.name == 'nt':
            abs_path = abs_path.replace('\\', '/')
        
        print(f"\n[Unable to open natively. Click to open]: file://{abs_path}\n")
