# Contributing to zotero-cli

Thanks for helping. zotero-cli is maintained by volunteers, so replies are best effort: expect days, not hours.

## Before you start

- **Questions** ("how do I…?"): open an issue with the **Question** form. It gets the `question` label.
- **Bugs and ideas**: open an issue with the matching form first. For anything beyond a small fix, please agree on the approach in the issue before writing a large pull request.
- **Security problems**: don't open a public issue. See [SECURITY.md](SECURITY.md).
- By taking part you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Set up

You need [uv](https://docs.astral.sh/uv/). It reads `.python-version` and `uv.lock`, so everyone gets the same interpreter and dependency versions.

```bash
git clone https://github.com/fchicout/zotero-cli.git
cd zotero-cli
uv sync --extra dev
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
git config blame.ignoreRevsFile .git-blame-ignore-revs   # keeps `git blame` useful past the format commit
```

The hooks run ruff (check and format), mypy and bandit on every commit and the unit tests on every push (`.pre-commit-config.yaml`). Changing a dependency means `uv add` / `uv remove` (never edit `pyproject.toml` or `uv.lock` by hand), and `uv.lock` is committed with it.

## The checks every change must pass

```bash
uv run ruff check .
uv run ruff format --check .      # `uv run ruff format .` fixes it
uv run mypy .
uv run bandit -q -r src
uv run pytest tests/unit tests/docs
```

CI runs the same, plus the unit tests on the oldest supported Python, a dependency vulnerability audit and a SonarQube quality gate. Run `pip-audit` locally with:

```bash
uv export --locked --no-dev --no-hashes --no-emit-project -o /tmp/req.txt \
  && uvx --from pip-audit==2.10.1 pip-audit -r /tmp/req.txt --no-deps --disable-pip
```

### Tests

- `tests/unit` is fast, offline and isolated: it never touches your real config or the network, and a test that tries to reach the network fails. Don't work around that; fake the service.
- `tests/docs` checks that the documentation matches the CLI (every command and flag documented, nothing documented that doesn't exist).
- `tests/e2e` talks to a **real** Zotero library and real services. It is skipped unless you opt in with `ZOTERO_CLI_E2E=1` and name a sandbox library in `ZOTERO_CLI_E2E_LIBRARY_ID`, and it writes to that library. Never point it at a library you care about, and never run it from a script, a scheduled job or a hook.
- `zotero-cli serve` exposes your library over HTTP: start it yourself, deliberately, never from automation.

### Architecture rules the tests enforce

Code is layered `cli` → `infra` → `core` (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)); `tests/unit/test_architecture.py` fails if `core` imports `infra` or `cli`, if `infra` imports `cli`, if `core` uses `rich`, if a `print()` is added to `core`, `infra` or `api` (services report through a `notify` sink or logging), or if a new service takes the whole `ZoteroGateway` instead of the narrow repository interfaces. Text from a Zotero library is untrusted: wrap it in `safe_markup()` before it goes into Rich markup (a test checks this too).

## Changes that touch the command line

If you add or change a command or flag, update in the same pull request: the command table in `README.md`, `docs/commands/*.md`, `docs/help_specs/*.md` (and Mermaid diagrams if the flow changed), then run `pytest tests/docs`. Add a line to the `[Unreleased]` section of `CHANGELOG.md`.

## Destructive commands

Every command that deletes, or changes many items at once, follows one policy:

1. **Preview by default.** It shows what it would do and changes nothing until `--execute`. (`item delete` names one item, like `rm FILE`, and deletes without `--execute`.)
2. **Confirm bulk permanent deletes.** With `--execute`, a bulk delete asks for confirmation; `--yes` skips the question. Without a terminal and without `--yes` it refuses with exit status 2 (`cli/safety.py`).
3. **`--force` only ever skips a prompt.** It never means "apply".
4. **Resolve targets unambiguously first.** A collection name that matches several collections is refused.
5. **Never delete more than asked for.** Items also filed outside the target are kept unless the user opts in (`--include-shared`). A step that depends on an earlier one (deleting a source after copying it, deleting a duplicate after moving its notes) runs only if the earlier step fully succeeded.
6. **Honor versions.** Deletes send the object's own version; if it changed since, nothing is deleted and the command fails.
7. **Review every new delete path.** `tests/unit/test_destructive_paths.py` fails when a new file calls a delete method, until the path has a gate and is added to its reviewed list.

## Pull requests

- Branch names: `feat/<issue>-<slug>`, `fix/<issue>-<slug>`, `chore/<issue>-<slug>`, `docs/<issue>-<slug>`.
- Commit messages: `type(scope): description (Issue #123)`, for example `fix(merge): keep duplicates whose children failed to move (Issue #549)`.
- Keep a pull request to one concern. Link the issue; say what you ran. The pull request template has the checklist.
- A bug fix should come with a test that fails without the fix.

## How releases work

zotero-cli follows [Semantic Versioning](https://semver.org/); [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) says what counts as the public interface and how deprecations work. Work ships in trains: patch releases first, then the next minor, then the next major, and `main` is always the next release. Issues carry a `semver: patch|minor|major` label and a milestone for the version that will carry them; maintainers decide which train a change belongs to, so a feature may wait for the next minor.

Maintainers cut a release with a version-bump pull request (`pyproject.toml`, `src/zotero_cli/__init__.py`, `uv.lock`'s own version line, and `CHANGELOG.md`), then tag `vX.Y.Z` on `main`; the tag triggers the release workflow (binaries, GitHub release, PyPI as `zotero-command-line`).

## License

By contributing you agree that your contributions are licensed under the project's [MIT License](LICENSE).
