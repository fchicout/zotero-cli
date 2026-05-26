import sys

# Set optional dependencies to None in sys.modules globally if not installed.
# This ensures importlib.util.find_spec() returns None cleanly on all Python versions (including Python 3.10 on CI).
try:
    import soundfile  # noqa: F401
except ImportError:
    sys.modules["soundfile"] = None

try:
    import openpyxl  # noqa: F401
except ImportError:
    sys.modules["openpyxl"] = None

try:
    import odf  # noqa: F401
except ImportError:
    sys.modules["odf"] = None
    sys.modules["odf.opendocument"] = None
    sys.modules["odf.table"] = None
    sys.modules["odf.text"] = None
