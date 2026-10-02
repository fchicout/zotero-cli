Closes #

## What and why

<!-- What changes, and why. Link the issue; for a larger change, the issue should already agree on the approach. -->

## Checklist

- [ ] `ruff check .`, `ruff format --check .`, `mypy .`, `bandit -q -r src` pass
- [ ] `pytest tests/unit tests/docs` passes, and a bug fix has a test that fails without it
- [ ] Commands or flags changed: `README.md`, `docs/commands/`, `docs/help_specs/` updated
- [ ] A line in the `[Unreleased]` section of `CHANGELOG.md`
- [ ] Anything that deletes follows the destructive-commands policy in `CONTRIBUTING.md`
- [ ] I did not run `tests/e2e` or `zotero-cli serve` against a library I care about
