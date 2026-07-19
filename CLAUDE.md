# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`zotero-cli` is a Python CLI (`zotero-cli` entry point, Python 3.10+) that combines two things:
1. **Direct Zotero library management** (items, collections, tags, storage, a local FastAPI bridge server).
2. **Systematic Literature Review (SLR) tooling** implementing the Kitchenham/Wohlin protocol: screening, decisions recorded as immutable SDB (Standardized Decision Block) notes, PRISMA reporting, snowball citation discovery, and RAG-based knowledge retrieval over the library.

## Commands

This project uses [uv](https://docs.astral.sh/uv/), not pip/bare venv, for dependency management — `uv.lock` is the source of truth for exact resolved versions and must be committed alongside any `pyproject.toml` dependency change. `.python-version` pins the project to Python 3.10 (matches CI); `uv sync` will download that interpreter if it isn't already available.

```bash
# Install for development (creates .venv/, installs from uv.lock, installs the project in editable mode)
uv sync --extra dev

# One-time: activate the pre-commit/pre-push hooks (ruff+mypy+bandit on commit, pytest tests/unit on push)
uv run pre-commit install --hook-type pre-commit --hook-type pre-push

# Run the CLI
zotero-cli <command> ...
# or during development
uv run zotero-cli <command> ...
uv run python -m zotero_cli.cli.main <command> ...

# Lint / format / type-check (must all pass before committing)
uv run ruff check .
uv run ruff check . --fix
uv run mypy .

# Security/dependency checks
uv run bandit -r src/
uv run safety check

# Tests — categorized via scripts/test_runner.sh [unit|e2e|docs|all] [true|false coverage]
uv run pytest tests/unit                                   # fast, isolated logic tests
uv run pytest tests/e2e                                     # hits real external APIs/state
uv run pytest tests/docs                                    # doc/repo-structure consistency checks
uv run pytest tests/unit --cov=src/zotero_cli --cov-report=xml   # matches CI coverage run

# Run a single test
uv run pytest tests/unit/core/test_attachment_service.py::test_looks_like_pdf -v

# Add/remove a dependency (updates pyproject.toml + uv.lock together — don't hand-edit either)
uv add <package>
uv add --optional dev <package>
uv remove <package>
```

CI (`.github/workflows/tests.yml`) runs `ruff check .`, `mypy .`, then `pytest tests/unit` with coverage, followed by a SonarQube scan/quality gate. Only `tests/unit` runs in CI — `tests/e2e` needs live credentials/network and is not gated automatically.

Test markers (see `pyproject.toml`): `unit`, `e2e`, `docs`.

## Configuration

The CLI reads `~/.config/zotero-cli/config.toml` (Linux/macOS) or `%APPDATA%\zotero-cli\config.toml` (Windows); see `config.toml.example`. A custom path can be passed via `--config`. Key fields: `api_key`, `library_id`, `library_type` (`user`/`group`), `user_id`, plus optional keys for Semantic Scholar, Unpaywall, NCBI, embedding/LLM providers, etc. `--offline` mode reads a local `zotero.sqlite` instead of calling the API (requires `database_path` in config).

## Architecture

Hexagonal (Ports & Adapters) layering under `src/zotero_cli/`:

- **`cli/`** — Argument parsing and user-facing I/O only. `cli/main.py` builds the `argparse` tree from commands self-registered via `cli/base.py`'s `CommandRegistry` (a `@CommandRegistry.register` decorator on a `BaseCommand` subclass). `cli/commands/*_cmd.py` holds one file per top-level noun (`item`, `collection`, `slr`, `report`, `rag`, `import`, `search`, `system`, `tag`, `storage`, `serve`, `find-pdf`); `cli/commands/slr/` holds SLR sub-verbs (`screen`, `decide`, `load`, `sdb`, `snowball`, ...). `cli/tui/` has Rich-based interactive screens (e.g. the screening TUI). `cli/presenters/` formats output.
- **`core/`** — Domain layer: `core/interfaces.py` defines the repository/gateway/service Protocols (`ZoteroGateway`, `ItemRepository`, `CollectionRepository`, `TagRepository`, `NoteRepository`, `AttachmentRepository`, `PDFResolver`, `EmbeddingProvider`, `LLMProvider`, `VectorRepository`, `RAGService`, ...). `core/models.py` / `core/zotero_item.py` hold domain models. `core/config.py` loads `ZoteroConfig`. Business logic lives in `core/services/*.py` (one service per concern — attachment, screening, extraction, audit, purge, tag, import, export, backup/restore, pdf finder, snowball, RAG, etc.) and `core/services/slr/*.py` (orchestrator, integrity, csv_inbound, snapshot, citation, status) plus `core/services/sdb/sdb_service.py` for the audit-trail notes.
- **`infra/`** — Adapters implementing `core/interfaces.py` against real systems: `zotero_api.py` (Zotero Web API via `requests`), `sqlite_repo.py` (offline-mode gateway), external metadata API clients (`crossref_api.py`, `semantic_scholar_api.py`, `openalex_api.py`, `pubmed_api.py`, `dblp_api.py`, `hal_api.py`, `eric_api.py`, `zbmath_api.py`, `inspire_hep_api.py`, `bdtd_api.py`, `unpaywall_api.py`), file-format gateways (`bibtex_lib.py`, `ris_lib.py`, `*_csv_lib.py`), and `sqlite_vector_repo.py` for RAG embeddings.
- **`infra/factory.py`** (`GatewayFactory`) — the single dependency-injection point. CLI commands call `GatewayFactory.get_<thing>(...)` rather than instantiating services directly. Internally `GatewayFactory` is a thin facade delegating to 5 focused sub-factories in the same package — `repository_factory.py` (`RepositoryFactory`: the core gateway + narrow Item/Collection/Tag/Note/Attachment repositories), `metadata_client_factory.py` (`MetadataClientFactory`: external bibliographic API clients + file-format import/export gateways), `resolver_factory.py` (`ResolverFactory`: PDF resolvers + snowball discovery), `ai_provider_factory.py` (`AIProviderFactory`: RAG/embedding/LLM providers), and `service_factory.py` (`ServiceFactory`: the domain services). When adding a new service or external client, wire it into whichever sub-factory owns that concern (`GatewayFactory` itself just needs a one-line delegating method added).
- **`api/`** — FastAPI app (`serve` command) exposing the library over HTTP for local scripts/dashboards.

### Metadata aggregation pattern

Enrichment queries multiple external sources in parallel and merges results (see `docs/ARCHITECTURE.md`'s sequence diagram): `MetadataAggregatorService` fans out to whichever provider clients are configured (Semantic Scholar, CrossRef, Unpaywall, OpenAlex, PubMed, etc.) and merges/deduplicates the results into a single `ResearchPaper`. New metadata providers follow the same shape: an `infra/<name>_api.py` client + registration in `GatewayFactory.get_metadata_aggregator`.

### SLR / SDB workflow

Screening decisions are written back into Zotero as immutable JSON notes (SDB v1.2) via `SDBService`, giving a machine-readable, per-item audit trail (reviewer persona, phase, exclusion criteria). `report snapshot` produces a versioned JSON audit artifact (schema documented in `docs/ARCHITECTURE.md`) capturing the full state of a collection at a point in time. `slr verify`/`slr prune`/`slr shift` check integrity of the Included/Excluded sets and detect drift between snapshots.

## Development Process

Documented in full in `docs/PROCESS.md` ("The Golden Path"). Key points relevant to code changes:

- Branch naming: `feat/<issue-id>-<slug>`, `fix/...`, `chore/...`.
- Before committing, code must pass the full gate: `ruff check .`, `mypy .`, `bandit -r src/`, `safety check`, `pytest tests/unit`, and any relevant integration/e2e tests.
- Commit style: `type(scope): description (Issue #ID)`.
- If a change touches CLI args or workflow, update `README.md`'s command table and `docs/commands/*.md` (and Mermaid diagrams if flow changed) — these command docs are also asserted against by `tests/docs`.
- Version bumps touch both `pyproject.toml` and `src/zotero_cli/__init__.py`; changelog entries go in `CHANGELOG.md`.

## Agent safety boundaries

`tests/e2e` (hits real external APIs/live Zotero state) and `zotero-cli serve` (binds an unauthenticated HTTP server — see `src/zotero_cli/api/`) must **always** require explicit, in-the-moment human invocation. Never run either from an autonomous loop, a scheduled/cron-triggered agent, a git hook, or any other unattended trigger — only when a human directly asks for it in the current turn. `tests/unit` and `tests/docs` have no such restriction. If a hook or automation surface is ever added to this repo, it must not expand to cover `tests/e2e` or `serve` without the user explicitly widening this rule.

`serve`'s lack of authentication (tracked separately, not a harness concern) is exactly why the boundary matters: an autonomous process that started it unattended could expose read/write access to the live Zotero library to anything reaching the bound host.

PR review is manual and on-demand (`gh pr diff`/`gh pr checkout` fed into an interactive session) — there is no CI-triggered AI review bot in this repo, and none should be added without the user explicitly deciding to take on the separate Anthropic API billing that a non-interactive CI job would require (distinct from a Claude Code subscription seat, which only covers interactive sessions).

## Status and roadmap: source of truth

Never hand-narrate project status, quality-gate results, or roadmap state — this repo has a documented history of exactly that drifting silently out of sync with reality (see `docs/archive/README.md`). Instead:

- **Pass/fail, coverage, lint/type status** → run `ruff check .`, `mypy .`, `pytest tests/unit` (with `--cov` if coverage is asked for) and report what actually happened. Never assert a quality-gate verdict without having just run it.
- **Backlog, roadmap, "what's next"** → `gh issue list --state open --repo fchicout/zotero-cli` (label taxonomy: `type:{feature,bug,chore,docs,architecture}`, `prio:{critical,high,medium,low}`, `comp:{cli,core,infra,slr}`). GitHub Issues is the roadmap; there is no separate hand-maintained roadmap file.
- **Architecture/process guidance** → this file and `docs/ARCHITECTURE.md` / `docs/PROCESS.md`.
- `docs/archive/` holds retired status/audit/roadmap documents from a prior persona-driven workflow, kept for historical record only — never treat anything in there as current.

## Repository notes

- `scratch/` is a gitignored/excluded scratch area (excluded from mypy) for ad hoc debugging scripts and analysis dumps. **Never write decrypted or long-lived credentials there** — no session cookies, tokens, passwords, or secret exports, even temporarily. It has held live plaintext secrets before (Infisical tokens, LDAP/SonarQube passwords, decrypted browser cookies, a hardcoded SonarQube JWT, a hardcoded Chrome Safe-Storage master key); those were purged. Any script that needs auth material must read it from an environment variable at runtime — see `scratch/fetch_sonar_api.py` / `scratch/read_sonar_with_cookies.js` (manual SONAR_JWT_SESSION/SONAR_XSRF_TOKEN) and `scratch/get_infisical_access_token.py` (Infisical `ansible-cli-identity` Machine Identity via Universal Auth — reuse this identity for any new Infisical tooling, don't invent another) for the pattern. Never hardcode or dump secret material to a file in this directory; scripts that fetch third-party secrets (e.g. `fetch_infisical_secrets.py`, `fetch_ws_secrets.py`) must only persist masked previews, never raw values.
- Coverage/Sonar config excludes CLI/TUI presentation layers and a few legacy services from the coverage gate (`sonar-project.properties`); domain/core services are expected to carry the bulk of test coverage.
