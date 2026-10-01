"""SonarQube must follow the release version, not a value frozen in the repo.

`sonar.projectVersion` sat at 2.8.0 through every release since; with the
"previous version" new-code period the baseline only moves when it changes.
"""

from pathlib import Path

import tomllib

REPO = Path(__file__).resolve().parents[2]


def test_properties_do_not_hard_code_a_version():
    lines = (REPO / "sonar-project.properties").read_text(encoding="utf-8").splitlines()
    active = [ln for ln in lines if ln.strip().startswith("sonar.projectVersion")]
    assert active == []


def test_ci_passes_the_pyproject_version_to_the_scan():
    workflow = (REPO / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "-Dsonar.projectVersion=${{ steps.version.outputs.value }}" in workflow
    assert "['project']['version']" in workflow


def test_the_version_the_workflow_reads_exists():
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"]
