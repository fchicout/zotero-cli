<!-- BADGES_START -->
![Version](https://img.shields.io/github/v/release/fchicout/zotero-cli)
![Build Status](https://github.com/fchicout/zotero-cli/actions/workflows/release.yml/badge.svg)
![Tests](https://github.com/fchicout/zotero-cli/actions/workflows/tests.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey) ![Python](https://img.shields.io/badge/python-3.11+-blue)
<!-- BADGES_END -->

# zotero-cli

> **Your Zotero library, from the command line.**

`zotero-cli` lets you read, organize and change a Zotero library without opening the Zotero app. Every operation is a plain command, so you can put it in shell scripts, cron jobs and CI, or hand it to an LLM agent as a tool.

It talks to the Zotero Web API (personal and group libraries). It can also read your local `zotero.sqlite` offline.

## Why a CLI for Zotero?

- **Scriptable:** items, collections, tags, notes and attachments are all reachable from a terminal, with no GUI steps in between.
- **Machine-readable output:** `item list` prints `json`, `csv` or `markdown`, and `--fields` picks the columns. Data goes to stdout and warnings to stderr, so you can pipe it into `jq`, a spreadsheet or a prompt.
- **Suited to LLM agents:** an agent can run `--help` on any command to learn how to use it, since each one includes worked examples. `item export --format md` converts an item's PDF into Markdown an LLM can read.
- **Safe by default:** bulk or destructive commands (`tag purge`, `item merge`, `item pdf strip`, `slr dedupe`, ...) only show a preview until you add `--execute`. `item hydrate` previews until you add `--execute`, `system restore` has `--dry-run`, and `collection purge` asks for confirmation. `--offline` reads the local database and is read-only apart from trash/restore.
- **Runs anywhere:** a single binary for Linux and Windows, no Python needed. Also available as a container or a Python package.

## What it can do

### Library management
- **Items:** list, inspect, add, update, move, merge duplicates, trash/restore, delete, and copy between libraries.
- **Collections:** create, rename, nest, empty, delete, and export whole collections (BibTeX, RIS, Markdown).
- **Tags:** list, add, and bulk-remove tags across a collection.
- **Search:** by DOI or title substring.
- **Attachments:** fetch missing PDFs from open-access sources, attach local files, strip attachments, and move stored files out to local or network storage while keeping them linked (`storage checkout`).

### Import and metadata
- **Import** from arXiv, DOI, BibTeX/RIS/CSV files, the Brazilian BDTD thesis repository, or manual entry.
- **Metadata lookup** from Semantic Scholar, CrossRef, OpenAlex, PubMed, Unpaywall and more when importing by DOI, and `item hydrate` to fill in empty fields (abstract, venue, date, authors, DOI) for items you already have, including published versions of arXiv preprints.
- **Library health reports:** duplicates, missing PDFs, DOIs or abstracts, disk usage, and checking the citations in a LaTeX manuscript against the library.

### Operations
- **Backup and restore** the whole library, or one collection, as a compressed `.zaf` archive, attachments included.
- **`system check`** tests the connection to every service you've configured (Zotero and the metadata providers) in one go.
- **Local HTTP API** (`serve`): read-only endpoints for items, collections and background jobs, for local scripts and dashboards.

### Optional: literature review toolkit
- **Systematic literature review (`slr`):** screening decisions recorded as auditable Zotero notes, PRISMA statistics, citation snowballing and data extraction. See [docs/commands/slr.md](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/slr.md).

## 🍳 Cookbook

### Get a collection as JSON
```bash
zotero-cli item list --collection "Reading List" --wide --format json | jq '.[] | {title, year, doi}'
```

### Choose exactly the columns you want
```bash
zotero-cli item list --collection "Reading List" --fields key,first_author,year,venue,DOI --format csv > reading.csv
```

### Add papers from a script
```bash
for doi in 10.1145/3290605.3300233 10.1038/nature14539; do
  zotero-cli import doi "$doi" --collection "Inbox"
done
zotero-cli item pdf fetch --collection "Inbox"
```

### Hand a paper to an LLM
```bash
# The item's PDF, converted to Markdown
zotero-cli item export --key ABCD1234 --format md --output ./context/
```

### Clean up tags, previewing before you change anything
```bash
zotero-cli tag purge --collection "Old Project"            # preview only
zotero-cli tag purge --collection "Old Project" --execute  # apply
```

### Query your library without internet access
```bash
# Reads the local zotero.sqlite (set database_path in config.toml)
zotero-cli --offline item list --collection "Reading List" --format markdown
```

### Back up everything
```bash
zotero-cli system backup --output library_2026-09.zaf
zotero-cli system restore --file library_2026-09.zaf --dry-run
```

### Try it without touching your real library
```bash
zotero-cli system check          # is every configured service reachable?
zotero-cli system demo-sandbox   # disposable collection of sample papers
zotero-cli system demo-sandbox --clean
```

## 📚 Command Reference

| Noun | Description | Key Verbs |
| :--- | :--- | :--- |
| **[`init`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/init.md)** | Config wizard | `(default)` |
| **[`item`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/item.md)** | Items | `list`, `inspect`, `add`, `update`, `move`, `merge`, `export`, `pdf`, `hydrate`, `purge`, `delete` |
| **[`collection`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/collection.md)** | Folders | `list`, `create`, `rename`, `delete`, `clean`, `export`, `backup`, `purge` |
| **[`tag`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/tag.md)** | Tags | `list`, `add`, `purge` |
| **[`search`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/search.md)** | Finder | `--doi`, `--title` |
| **[`import`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/import.md)** | Ingest | `arxiv`, `doi`, `file`, `bdtd`, `manual` |
| **[`report`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/report.md)** | Library health | `duplicates`, `audit`, `stats`, `attachments`, `verify-latex` |
| **[`storage`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/storage.md)** | Attachments | `checkout` |
| **[`system`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/system.md)** | Operations | `info`, `check`, `groups`, `switch`, `backup`, `restore`, `jobs` |
| **[`serve`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/serve.md)** | Local HTTP API | `(default)` |
| **[`slr`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/slr.md)** | Literature review | `screen`, `decide`, `load`, `extract`, `snowball`, `sdb`, `report` |

Every command has built-in help with worked examples: `zotero-cli <noun> <verb> --help`.

---

## 📦 Installation

### Option 1: Standalone binaries (recommended)
Download a pre-built binary for your system. **You don't need Python.**

*   **Windows:** `.msi` installer or `.zip` from [Latest Releases](https://github.com/fchicout/zotero-cli/releases/latest).
*   **Linux (Ubuntu/Debian):** `.deb` package.
*   **Linux (Fedora/RHEL):** `.rpm` package.
*   **Any Linux:** `zotero-cli-linux-amd64.tar.gz`.

Or use the one-line installer scripts. They fetch the latest release (or the one named in `ZOTERO_CLI_VERSION`, e.g. `v2.8.12`) and check it against the release's `SHA256SUMS` before installing:
```bash
# Linux (amd64)
curl -fsSL https://raw.githubusercontent.com/fchicout/zotero-cli/main/install.sh | bash
```
```powershell
# Windows (PowerShell)
irm https://raw.githubusercontent.com/fchicout/zotero-cli/main/install.ps1 | iex
```

**Verifying a download yourself:** every release from v2.8.12 on includes a `SHA256SUMS` file and signed build provenance. With the [GitHub CLI](https://cli.github.com/), `gh attestation verify zotero-cli-linux-amd64.tar.gz -R fchicout/zotero-cli` confirms the file was built by this repository's release workflow.

### 🐍 Option 2: From PyPI (Python 3.11+)
The package is called **`zotero-command-line`** on PyPI, because the `zotero-cli` name there belongs to an older, unrelated project. The command it installs is still `zotero-cli`.

```bash
uv tool install zotero-command-line   # or: pipx install zotero-command-line
zotero-cli --help
```

### 🐳 Option 3: Containers
The repo includes a `Dockerfile`. It builds the same standalone binary as the releases.

```bash
git clone https://github.com/fchicout/zotero-cli.git
cd zotero-cli
docker build -t zotero-cli .

# Configure with an env file (ZOTERO_API_KEY=..., ZOTERO_LIBRARY_ID=..., one per line),
# which keeps keys out of your shell history...
docker run --rm --env-file zotero.env zotero-cli system info

# ...or mount your existing config directory, running as yourself so any
# files zotero-cli writes there (logs, job state) belong to you
docker run --rm --user "$(id -u):$(id -g)" \
  -v ~/.config/zotero-cli:/config/zotero-cli zotero-cli system info
```

The container runs as an unprivileged user and keeps its config in `/config/zotero-cli`. On SELinux hosts (Fedora, RHEL), add `:z` to the mount: `-v ~/.config/zotero-cli:/config/zotero-cli:z`.

> *Note: `--offline` mode (reading a local `zotero.sqlite`) needs that file mounted into the container too, e.g. `-v /path/to/zotero.sqlite:/data/zotero.sqlite`.*

> *Note: inside a container, `serve` has to bind `0.0.0.0` to be reachable, which needs `--allow-remote` (it prints an access token). Publish the port on the host's loopback only: `docker run -p 127.0.0.1:1969:1969 ... zotero-cli serve --host 0.0.0.0 --allow-remote`.*

A `.devcontainer/` configuration is also included for GitHub Codespaces and VS Code Dev Containers. It sets up the full development environment for contributing, not the lightweight image above.

### Option 4: From source (Python 3.11+)
Using [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/fchicout/zotero-cli.git
cd zotero-cli
uv tool install .
```

### 📦 Using `zotero-cli` as a Python library
```bash
pip install zotero-command-line
```
See the "Distribution" section of [docs/ARCHITECTURE.md](https://github.com/fchicout/zotero-cli/blob/main/docs/ARCHITECTURE.md) for details, including installing an unreleased commit from git.

### ⚙️ Configuration
```bash
zotero-cli init         # interactive wizard: API key, library, optional metadata providers
zotero-cli system info  # show which config is in use
```

The config file lives at `~/.config/zotero-cli/config.toml` (Linux/macOS) or `%APPDATA%\zotero-cli\config.toml` (Windows). See [docs/SETUP_GUIDE.md](https://github.com/fchicout/zotero-cli/blob/main/docs/SETUP_GUIDE.md) and `config.toml.example`.

## Development & Contribution

```bash
git clone https://github.com/fchicout/zotero-cli.git
cd zotero-cli
uv sync --extra dev
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
uv run pytest tests/unit
```

`uv sync` creates `.venv/`, using the Python version pinned in `.python-version`, and installs the project in editable mode from `uv.lock`. Commit `uv.lock` alongside any dependency change so everyone, CI included, gets exactly the same versions. `pre-commit install` sets up the checks from `docs/PROCESS.md`: ruff, mypy and bandit run on every `git commit`, and `pytest tests/unit` runs on `git push`. See `.pre-commit-config.yaml`.

## Security
To report a vulnerability, see [SECURITY.md](https://github.com/fchicout/zotero-cli/blob/main/SECURITY.md). Please don't use public issues for security problems.

## License
MIT License. See [LICENSE](https://github.com/fchicout/zotero-cli/blob/main/LICENSE) for details.
