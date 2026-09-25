"""Issue #405: the notices shipped with the binaries are generated from what
PyInstaller bundled, and generation fails rather than ship an incomplete file."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "gen_third_party_notices", ROOT / "scripts" / "gen_third_party_notices.py"
)
assert _spec and _spec.loader
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


def _write_build(tmp_path: Path, binaries, modules) -> Path:
    build = tmp_path / "build" / "zotero-cli"
    build.mkdir(parents=True)
    pkg_entries = [(name, src, "BINARY") for name, src in binaries]
    (build / "PKG-00.toc").write_text(repr((str(build / "x.pkg"), {}, pkg_entries)))
    pyz_entries = [(name, src, "PYMODULE") for name, src in modules]
    pyz_entries.append(("some.namespace", "-", "PYMODULE"))
    (build / "PYZ-00.toc").write_text(repr((str(build / "PYZ-00.pyz"), pyz_entries)))
    return build


def _installed_module(dist_module) -> str:
    return str(Path(dist_module.__file__).resolve())


def test_every_bundled_distribution_gets_its_licence_text(tmp_path):
    import rich
    import tenacity

    build = _write_build(
        tmp_path,
        binaries=[("libstdc++.so.6", "/lib64/libstdc++.so.6")],
        modules=[
            ("rich", _installed_module(rich)),
            ("tenacity", _installed_module(tenacity)),
            ("json", str(Path(sys.base_prefix) / "lib" / "json" / "__init__.py")),
        ],
    )
    out = tmp_path / "THIRD_PARTY_LICENSES.txt"

    assert gen.main(["--build-dir", str(build), "--output", str(out)]) == 0

    text = out.read_text()
    assert "rich " in text and "tenacity " in text
    assert "Permission is hereby granted" in text  # rich's MIT text
    assert "Python " in text and "runtime (CPython)" in text
    assert "OpenSSL (linked into the Python runtime)" in text
    assert "GCC RUNTIME LIBRARY EXCEPTION" in text


def test_an_unattributed_bundled_file_fails_generation(tmp_path, capsys):
    build = _write_build(tmp_path, binaries=[("libmystery.so", "/opt/vendor/libmystery.so")], modules=[])
    out = tmp_path / "THIRD_PARTY_LICENSES.txt"

    assert gen.main(["--build-dir", str(build), "--output", str(out)]) == 1
    assert "libmystery.so" in capsys.readouterr().err
    assert not out.exists()


@pytest.mark.parametrize(
    "library, expected",
    [
        ("libssl.so.3", "OpenSSL"),
        ("libcrypto.so.3", "OpenSSL"),
        ("libsqlite3.so.0", "SQLite"),
        ("libz.so.1", "zlib"),
        ("libzstd.so.1", "Zstandard"),
        ("libreadline.so.8", None),  # GPL-3.0: must be excluded from the build, not noticed
    ],
)
def test_distro_shared_libraries_map_to_their_licences(library, expected):
    assert gen._runtime_library(library) == expected


def test_distro_shared_library_is_noticed_without_the_static_set(tmp_path):
    build = _write_build(
        tmp_path, binaries=[("libssl.so.3", "/usr/lib/x86_64-linux-gnu/libssl.so.3")], modules=[]
    )
    out = tmp_path / "N.txt"

    assert gen.main(["--build-dir", str(build), "--output", str(out)]) == 0
    text = out.read_text()
    assert "OpenSSL (linked into the Python runtime)" in text
    assert "libedit" not in text


def test_every_static_licence_file_exists_and_is_not_empty():
    files = {entry[2] for entry in gen.PYTHON_RUNTIME_LIBRARIES}
    files |= {"gcc-runtime-library-exception-3.1.txt", "msvc-runtime.txt"}
    for name in files:
        path = gen.STATIC_LICENSES / name
        assert path.is_file() and path.stat().st_size > 100, name
