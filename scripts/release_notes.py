"""
Prints the GitHub release notes for a version: its CHANGELOG section plus how
to verify the downloads (Issue #416; the release used to show only the
auto-generated list of PR titles).

    python scripts/release_notes.py 3.0.6 [--changelog CHANGELOG.md]

Exits 1 if the CHANGELOG has no `## [<version>]` section, so a release can't
go out without its notes.
"""

import argparse
import re
import sys
from pathlib import Path

FOOTER = """
---

**Verifying downloads:** `SHA256SUMS` lists the checksum of every file
(`sha256sum -c SHA256SUMS --ignore-missing`). Each file also has signed build
provenance: `gh attestation verify <file> -R fchicout/zotero-cli` confirms it
was built by this repository's release workflow.

**PyPI:** `uv tool install zotero-command-line=={version}` (or `pipx install`).
"""


def section(changelog: str, version: str) -> str:
    """The body of `## [version]` (without the heading), up to the next
    `## [` heading or a link-reference block."""
    heading = re.compile(rf"^## \[{re.escape(version)}\][^\n]*\n", re.M)
    match = heading.search(changelog)
    if not match:
        raise LookupError(f"CHANGELOG has no section for {version}")
    rest = changelog[match.end() :]
    end = re.search(r"^## \[", rest, re.M)
    return (rest[: end.start()] if end else rest).strip()


def notes(changelog: str, version: str) -> str:
    return section(changelog, version) + "\n" + FOOTER.format(version=version)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("version", help="e.g. 3.0.6 (a leading v is ignored)")
    parser.add_argument("--changelog", default="CHANGELOG.md")
    args = parser.parse_args(argv)
    version = args.version.removeprefix("v")
    try:
        print(notes(Path(args.changelog).read_text(encoding="utf-8"), version))
    except LookupError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
