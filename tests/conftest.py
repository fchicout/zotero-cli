import sys

# Set optional dependencies to None in sys.modules globally if not installed.
# This ensures importlib.util.find_spec() returns None cleanly on all Python versions (including Python 3.10 on CI).
try:
    import soundfile  # noqa: F401
except ImportError:
    sys.modules["soundfile"] = None  # type: ignore[assignment]

try:
    import openpyxl  # noqa: F401
except ImportError:
    sys.modules["openpyxl"] = None  # type: ignore[assignment]

try:
    import odf  # noqa: F401
except ImportError:
    sys.modules["odf"] = None  # type: ignore[assignment]
    sys.modules["odf.opendocument"] = None  # type: ignore[assignment]
    sys.modules["odf.table"] = None  # type: ignore[assignment]
    sys.modules["odf.text"] = None  # type: ignore[assignment]

