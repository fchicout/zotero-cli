import os
import sys
from importlib.machinery import ModuleSpec
from unittest.mock import MagicMock

# Force deterministic Rich console output for capsys-based assertions in CLI tests.
# Rich's terminal-capability detection considers the invoking shell's TERM value
# (not just isatty()), so tests asserting plain-text substrings against captured
# output were flaky depending on whether the outer environment's TERM looked
# color-capable — passing in CI/GitHub Actions but failing in some interactive or
# sandboxed shells. Set before any app module (which may construct a module-level
# `Console()`) is imported.
os.environ["TERM"] = "dumb"
os.environ["NO_COLOR"] = "1"

# Global fallback mocks for optional dependencies on CI environments to prevent ModuleNotFoundError
try:
    import soundfile  # noqa: F401
except ImportError:
    mock_sf = MagicMock()
    mock_sf.__spec__ = ModuleSpec("soundfile", None)
    sys.modules["soundfile"] = mock_sf

try:
    import openpyxl  # noqa: F401
except ImportError:
    mock_xl = MagicMock()
    mock_xl.__spec__ = ModuleSpec("openpyxl", None)
    sys.modules["openpyxl"] = mock_xl

try:
    import odf  # noqa: F401
except ImportError:
    mock_odf = MagicMock()
    mock_odf.__spec__ = ModuleSpec("odf", None)
    sys.modules["odf"] = mock_odf
    sys.modules["odf.opendocument"] = mock_odf
    sys.modules["odf.table"] = mock_odf
    sys.modules["odf.text"] = mock_odf
