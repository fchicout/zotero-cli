"""Release notes come from the CHANGELOG (Issue #416)."""

from scripts import release_notes

CHANGELOG = """# Changelog

## [Unreleased]

### 🐛 Bug Fixes
- not released yet

## [3.0.5] - 2026-09-28

The fifth patch train.

### ⚡ Performance
- faster

## [3.0.4] - 2026-09-28

- older
"""


def test_the_section_of_the_version_only():
    body = release_notes.section(CHANGELOG, "3.0.5")
    assert body.startswith("The fifth patch train.")
    assert "- faster" in body
    assert "older" not in body
    assert "not released" not in body


def test_the_last_section_runs_to_the_end():
    assert release_notes.section(CHANGELOG, "3.0.4") == "- older"


def test_notes_add_verification_instructions():
    text = release_notes.notes(CHANGELOG, "3.0.5")
    assert "gh attestation verify" in text
    assert "zotero-command-line==3.0.5" in text


def test_a_missing_section_fails(tmp_path, capsys):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(CHANGELOG, encoding="utf-8")
    assert release_notes.main(["v9.9.9", "--changelog", str(path)]) == 1
    assert "no section for 9.9.9" in capsys.readouterr().err
    assert release_notes.main(["v3.0.5", "--changelog", str(path)]) == 0


def test_the_real_changelog_has_the_current_release():
    """The release job would fail otherwise."""
    from pathlib import Path

    import zotero_cli

    changelog = (Path(__file__).resolve().parents[2] / "CHANGELOG.md").read_text(encoding="utf-8")
    release_notes.section(changelog, zotero_cli.VERSION)  # raises LookupError if missing
