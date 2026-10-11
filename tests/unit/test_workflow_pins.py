"""Issue #593 (GHSA-9p5q-c7wc-vwxv): every workflow pins its actions to commit SHAs,
keeps the checkout token out of later steps and declares its permissions, so a moved
tag of a third-party action cannot run with this repository's secrets."""

import re
from pathlib import Path
from typing import Any, Iterator, Tuple

import pytest
import yaml

WORKFLOWS = sorted((Path(__file__).resolve().parents[2] / ".github" / "workflows").glob("*.yml"))
PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")


def _steps(workflow: dict) -> Iterator[Tuple[str, dict]]:
    for job_name, job in (workflow.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            yield job_name, step


def _load(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_the_workflows_exist():
    assert {p.name for p in WORKFLOWS} >= {"release.yml", "tests.yml", "tests-docs-only.yml"}


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_full_commit_sha(path: Path):
    unpinned = [
        f"{job}: {step['uses']}"
        for job, step in _steps(_load(path))
        if "uses" in step and not step["uses"].startswith("./") and not PINNED.match(step["uses"])
    ]

    assert unpinned == [], f"pin these to a commit SHA, keeping the tag in a comment: {unpinned}"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_checkouts_do_not_keep_the_token(path: Path):
    leaky = [
        job
        for job, step in _steps(_load(path))
        if str(step.get("uses", "")).startswith("actions/checkout@")
        and (step.get("with") or {}).get("persist-credentials") is not False
    ]

    assert leaky == [], f"set persist-credentials: false in: {leaky}"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_workflow_declares_its_permissions(path: Path):
    assert "permissions" in _load(path), "add a top-level permissions: block (contents: read)"
