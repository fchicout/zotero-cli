#!/usr/bin/env python3
"""
Writes THIRD_PARTY_LICENSES.txt for a PyInstaller build (Issue #405).

The notices must match what the binary actually contains, not the venv: this
reads PyInstaller's own record of the bundled files (PKG-00.toc / PYZ-00.toc
in the build directory), maps each file to the installed distribution that
owns it, and writes that distribution's licence texts. It then adds the
Python runtime (CPython's licence, plus the native libraries statically
linked into it), and the system runtime libraries PyInstaller copied in
(GCC runtime on Linux, the MSVC runtime on Windows).

A bundled file that can't be attributed - or a distribution with no licence
text - fails the run, so a new dependency can't ship without its notice.

Run it with the interpreter that ran PyInstaller:

    python scripts/gen_third_party_notices.py --build-dir build/zotero-cli \\
        --output dist/THIRD_PARTY_LICENSES.txt
"""

import argparse
import ast
import importlib.metadata as md
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

REPO = Path(__file__).resolve().parents[1]
STATIC_LICENSES = REPO / "packaging" / "licenses"

# This project itself: covered by LICENSE, shipped next to the notices.
OWN_DISTRIBUTIONS = {"zotero-command-line", "zotero-cli"}

# Native libraries the Python runtime uses: (name, licence, text file, shared
# library name prefixes). python-build-standalone (what uv installs, and CI
# builds with) links them all statically into libpython - detected in its
# symbols - so all are listed when the runtime is bundled. A distro Python
# (the Docker build) loads them as shared libraries that PyInstaller copies
# in; those are matched by file name.
PYTHON_RUNTIME_LIBRARIES: List[Tuple[str, str, str, Tuple[str, ...]]] = [
    ("OpenSSL", "Apache-2.0", "openssl.txt", ("libssl", "libcrypto")),
    ("SQLite", "Public domain", "sqlite.txt", ("libsqlite3", "sqlite3.dll")),
    ("libffi", "MIT", "libffi.txt", ("libffi",)),
    ("zlib", "Zlib", "zlib.txt", ("libz.", "zlib")),
    ("bzip2", "bzip2-1.0.6", "bzip2.txt", ("libbz2",)),
    ("XZ Utils (liblzma)", "0BSD", "xz.txt", ("liblzma",)),
    ("XZ Utils 0BSD text", "0BSD", "xz-0BSD.txt", ("liblzma",)),
    ("Expat", "MIT", "expat.txt", ("libexpat",)),
    ("mpdecimal", "BSD-2-Clause", "mpdecimal.txt", ("libmpdec",)),
    ("libedit", "BSD-3-Clause", "libedit.txt", ("libedit",)),
    ("ncurses", "X11-style (MIT)", "ncurses.txt", ("libncurses", "libtinfo", "libpanel", "libform", "libmenu")),
    ("Zstandard", "BSD-3-Clause (elected; dual-licensed with GPL-2.0)", "zstd.txt", ("libzstd",)),
    ("libuuid (util-linux)", "BSD-3-Clause", "libuuid.txt", ("libuuid",)),
    ("HACL*", "MIT OR Apache-2.0", "hacl-star.txt", ()),
]

LICENSE_FILE_MARKERS = ("LICEN", "COPYING", "NOTICE")


@dataclass
class Attribution:
    distributions: Set[str] = field(default_factory=set)
    uses_python_runtime: bool = False
    runtime_libraries: Set[str] = field(default_factory=set)
    gcc_runtime: Set[str] = field(default_factory=set)
    msvc_runtime: Set[str] = field(default_factory=set)
    unattributed: Set[str] = field(default_factory=set)


def bundled_files(build_dir: Path) -> List[Tuple[str, str]]:
    """(name inside the binary, source path) for every bundled file."""
    entries: List[Tuple[str, str]] = []
    pkg = ast.literal_eval((build_dir / "PKG-00.toc").read_text(encoding="utf-8"))
    entries += [(e[0], e[1]) for e in pkg[2]]
    for toc in sorted(build_dir.glob("PYZ-*.toc")):
        pyz = ast.literal_eval(toc.read_text(encoding="utf-8"))
        entries += [(e[0], e[1]) for e in pyz[1]]
    # Namespace packages have no file ("-"); options have no source ("").
    return [(dest, source) for dest, source in entries if source and source != "-"]


def _norm(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def file_owners() -> Dict[str, str]:
    owners: Dict[str, str] = {}
    for dist in md.distributions():
        name = dist.metadata["Name"]
        for f in dist.files or []:
            owners[_norm(str(dist.locate_file(f)))] = name
    return owners


def _runtime_library(base: str) -> Optional[str]:
    for name, _spdx, _file, prefixes in PYTHON_RUNTIME_LIBRARIES:
        if prefixes and base.startswith(prefixes):
            return name
    return None


def attribute(entries: Iterable[Tuple[str, str]], build_dir: Path) -> Attribution:
    owners = file_owners()
    runtime_root = _norm(sys.base_prefix)
    own_roots = [_norm(str(REPO / "src")), _norm(str(build_dir))]
    result = Attribution()
    for dest, source in entries:
        path = _norm(source)
        base = os.path.basename(dest).lower()
        library = _runtime_library(base)
        if path in owners:
            result.distributions.add(owners[path])
        elif base.startswith(("libgcc_s", "libstdc++")):
            result.gcc_runtime.add(base)
        elif base.startswith(("vcruntime", "msvcp", "concrt")):
            result.msvc_runtime.add(base)
        elif path.startswith(runtime_root):
            result.uses_python_runtime = True
        elif any(path.startswith(root) for root in own_roots):
            continue  # this project's own code and PyInstaller's generated files
        elif library:
            result.runtime_libraries.add(library)
        elif base.startswith(("libpython", "python3")) and base.split(".")[0][-1:].isdigit():
            result.uses_python_runtime = True  # a distro's libpython under /usr/lib
        else:
            result.unattributed.add(f"{dest} <- {source}")
    result.distributions -= OWN_DISTRIBUTIONS
    return result


def license_name(dist: md.Distribution) -> str:
    meta = dist.metadata
    expression = meta.get("License-Expression")
    if expression:
        return str(expression)
    classifiers = [
        c.split("::")[-1].strip()
        for c in meta.get_all("Classifier") or []
        if c.startswith("License ::")
    ]
    if classifiers:
        return ", ".join(classifiers)
    text = (meta.get("License") or "").strip()
    return text.splitlines()[0] if text else "see licence text below"


def license_texts(dist: md.Distribution) -> List[Tuple[str, str]]:
    texts = []
    for f in dist.files or []:
        name = os.path.basename(str(f)).upper()
        if ".dist-info" not in str(f) and "LICENSES" not in str(f).upper():
            continue
        if any(marker in name for marker in LICENSE_FILE_MARKERS):
            path = Path(str(dist.locate_file(f)))
            if path.is_file():
                texts.append((str(f), path.read_text(encoding="utf-8", errors="replace")))
    return texts


def python_runtime_license() -> Optional[Path]:
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    for candidate in (
        Path(sys.base_prefix) / "lib" / version / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sys.base_prefix) / "Lib" / "LICENSE.txt",
    ):
        if candidate.is_file():
            return candidate
    return None


RULE = "=" * 78
THIN = "-" * 78


def _section(out: List[str], title: str, body: str) -> None:
    out += [RULE, title, RULE, "", body.strip(), "", ""]


def render(attribution: Attribution) -> Tuple[str, List[str]]:
    """The notices text, and the problems that make it incomplete."""
    problems = [f"unattributed bundled file: {u}" for u in sorted(attribution.unattributed)]
    out = [
        "zotero-cli - third-party software notices",
        "",
        "This binary bundles the software listed below. Each component is",
        "distributed under its own licence, reproduced here. zotero-cli itself",
        "is MIT-licensed; see LICENSE.",
        "",
        "Where a component is offered under a choice of licences, it is",
        "distributed here under the permissive option: bibtexparser under BSD,",
        "Zstandard under BSD-3-Clause. No component has been modified.",
        "",
        "",
    ]

    for name in sorted(attribution.distributions, key=str.lower):
        dist = md.distribution(name)
        texts = license_texts(dist)
        if not texts:
            problems.append(f"no licence text found for distribution {name}")
            continue
        header = f"{dist.metadata['Name']} {dist.version}  -  {license_name(dist)}"
        body = f"\n\n{THIN}\n".join(f"[{path}]\n\n{text.strip()}" for path, text in texts)
        _section(out, header, body)

    if attribution.uses_python_runtime:
        cpython = python_runtime_license()
        if cpython is None:
            problems.append("CPython LICENSE.txt not found under sys.base_prefix")
        else:
            _section(
                out,
                f"Python {sys.version.split()[0]} runtime (CPython)  -  PSF-2.0",
                cpython.read_text(encoding="utf-8", errors="replace"),
            )

    for lib, spdx, filename, _prefixes in PYTHON_RUNTIME_LIBRARIES:
        # No shared copies found: python-build-standalone, which links all of
        # them statically into the bundled runtime.
        linked = attribution.uses_python_runtime and not attribution.runtime_libraries
        if linked or lib in attribution.runtime_libraries:
            text_path = STATIC_LICENSES / filename
            if not text_path.is_file():
                problems.append(f"missing {text_path}")
                continue
            _section(
                out,
                f"{lib} (linked into the Python runtime)  -  {spdx}",
                text_path.read_text(encoding="utf-8"),
            )

    if attribution.gcc_runtime:
        _section(
            out,
            f"GCC runtime libraries ({', '.join(sorted(attribution.gcc_runtime))})"
            "  -  GPL-3.0-or-later WITH GCC-exception-3.1",
            "These libraries are distributed under the GNU General Public License,\n"
            "version 3 or later, with the GCC Runtime Library Exception, which\n"
            "permits distributing them as part of this program. Source:\n"
            "https://gcc.gnu.org/.\n\n"
            + (STATIC_LICENSES / "gcc-runtime-library-exception-3.1.txt").read_text(
                encoding="utf-8"
            ),
        )

    if attribution.msvc_runtime:
        _section(
            out,
            f"Microsoft Visual C++ runtime ({', '.join(sorted(attribution.msvc_runtime))})",
            (STATIC_LICENSES / "msvc-runtime.txt").read_text(encoding="utf-8"),
        )

    return "\n".join(out), problems


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    attribution = attribute(bundled_files(args.build_dir), args.build_dir)
    text, problems = render(attribution)
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(
        f"Wrote {args.output}: {len(attribution.distributions)} distributions, "
        f"Python runtime: {attribution.uses_python_runtime}, "
        f"GCC runtime: {sorted(attribution.gcc_runtime)}, "
        f"MSVC runtime: {sorted(attribution.msvc_runtime)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
