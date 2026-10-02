<!-- BADGES_START -->
![Version](https://img.shields.io/github/v/release/fchicout/zotero-cli)
![Build Status](https://github.com/fchicout/zotero-cli/actions/workflows/release.yml/badge.svg)
![Tests](https://github.com/fchicout/zotero-cli/actions/workflows/tests.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey) ![Python](https://img.shields.io/badge/python-3.11+-blue)
<!-- BADGES_END -->
<!-- SonarQube badges: images from the `badges` branch, refreshed by .github/workflows/sonar-badges.yml (Issue #505) -->
[![Quality Gate](https://raw.githubusercontent.com/fchicout/zotero-cli/badges/quality_gate.svg)](https://sonar.fchicout.dev/dashboard?id=zotero-cli) [![Coverage](https://raw.githubusercontent.com/fchicout/zotero-cli/badges/coverage.svg)](https://sonar.fchicout.dev/dashboard?id=zotero-cli) [![Bugs](https://raw.githubusercontent.com/fchicout/zotero-cli/badges/bugs.svg)](https://sonar.fchicout.dev/dashboard?id=zotero-cli) [![Vulnerabilities](https://raw.githubusercontent.com/fchicout/zotero-cli/badges/vulnerabilities.svg)](https://sonar.fchicout.dev/dashboard?id=zotero-cli) [![Code Smells](https://raw.githubusercontent.com/fchicout/zotero-cli/badges/code_smells.svg)](https://sonar.fchicout.dev/dashboard?id=zotero-cli) [![Duplicated Lines](https://raw.githubusercontent.com/fchicout/zotero-cli/badges/duplicated_lines_density.svg)](https://sonar.fchicout.dev/dashboard?id=zotero-cli) [![Maintainability](https://raw.githubusercontent.com/fchicout/zotero-cli/badges/sqale_rating.svg)](https://sonar.fchicout.dev/dashboard?id=zotero-cli) [![Reliability](https://raw.githubusercontent.com/fchicout/zotero-cli/badges/reliability_rating.svg)](https://sonar.fchicout.dev/dashboard?id=zotero-cli) [![Security](https://raw.githubusercontent.com/fchicout/zotero-cli/badges/security_rating.svg)](https://sonar.fchicout.dev/dashboard?id=zotero-cli) [![Security Hotspots](https://raw.githubusercontent.com/fchicout/zotero-cli/badges/security_hotspots.svg)](https://sonar.fchicout.dev/dashboard?id=zotero-cli) [![Technical Debt](https://raw.githubusercontent.com/fchicout/zotero-cli/badges/sqale_index.svg)](https://sonar.fchicout.dev/dashboard?id=zotero-cli) [![Lines of Code](https://raw.githubusercontent.com/fchicout/zotero-cli/badges/ncloc.svg)](https://sonar.fchicout.dev/dashboard?id=zotero-cli)

# zotero-cli

> **Your Zotero library, from the command line.**

`zotero-cli` lets you read, organize and change a Zotero library without opening the Zotero app. Every operation is a plain command, so you can put it in shell scripts, cron jobs and CI, or hand it to an LLM agent as a tool.

It talks to the Zotero Web API (personal and group libraries). It can also read your local `zotero.sqlite` offline.

## Why a CLI for Zotero?

- **Scriptable:** items, collections, tags, notes and attachments are all reachable from a terminal, with no GUI steps in between.
- **Machine-readable output:** `item list` prints `json`, `csv` or `markdown`, and `--fields` picks the columns. Data goes to stdout and messages to stderr, so you can pipe it into `jq`, a spreadsheet or a prompt.
- **Suited to LLM agents:** an agent can run `--help` on any command to learn its options, and most commands' help includes worked examples. `item export --as md` extracts the text of an item's PDF into a `.md` file an LLM can read.
- **Preview first:** `collection clean`, `collection delete --recursive`, `slr prune`, `slr load`, `tag purge`, `item merge`, `item hydrate`, `item pdf strip` and `slr dedupe` only show what they would do until you add `--execute`. A recursive delete also asks for confirmation (`--yes` in scripts), and a collection name that matches several collections is refused rather than guessed. `item purge` and `collection purge` ask for confirmation. `item delete`, `storage checkout` and `system restore` predate this policy and still apply immediately without a flag (a deprecation warning says so); pass their `--execute`, or `--dry-run` to preview first - this changes to preview-by-default in 4.0. `--offline` reads the local database and is read-only apart from trash/restore.
- **Runs anywhere:** a single binary for Linux and Windows, no Python needed. Also available as a container or a Python package.

## What it can do

### Library management
- **Items:** list, inspect, add, update, move, merge duplicates, trash/restore, delete, and copy between libraries.
- **Collections:** create, rename, nest, empty, delete, and export whole collections (BibTeX, RIS, Markdown, or a formatted bibliography in any CSL style).
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
# The text of the item's PDF, saved as .md
zotero-cli item export --key ABCD1234 --as md --output ./context/
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
| **[`item`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/item.md)** | Items | `list`, `inspect`, `add`, `update`, `move`, `merge`, `export`, `pdf`, `hydrate`, `purge`, `delete`, `trash`, `restore`, `transfer` |
| **[`collection`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/collection.md)** | Folders | `list`, `create`, `rename`, `delete`, `clean`, `export`, `backup`, `purge` |
| **[`tag`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/tag.md)** | Tags | `list`, `add`, `purge` |
| **[`search`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/search.md)** | Finder | `--doi`, `--title` |
| **[`import`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/import.md)** | Ingest | `arxiv`, `doi`, `file`, `bdtd`, `manual` |
| **[`report`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/report.md)** | Library health | `duplicates`, `audit`, `stats`, `attachments`, `verify-latex` |
| **[`storage`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/storage.md)** | Attachments | `checkout` |
| **[`system`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/system.md)** | Operations | `info`, `check`, `selftest`, `groups`, `switch`, `backup`, `verify`, `restore`, `normalize`, `demo-sandbox`, `jobs` |
| **[`serve`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/serve.md)** | Local HTTP API | `(default)` |
| **[`slr`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/slr.md)** | Literature review | `source`, `screen`, `decide`, `load`, `list`, `reconcile`, `promote`, `dedupe`, `prune`, `extract`, `snowball`, `sdb`, `report` |
| **[`rag`](https://github.com/fchicout/zotero-cli/blob/main/docs/commands/rag.md)** | Semantic search (optional `rag` extra; **deprecated**, moving to a separate tool and removed in 4.0) | `ingest`, `query`, `context`, `purge`, `model` |

Every command has built-in help: `zotero-cli <noun> <verb> --help`. Every example in these docs is checked against the real command-line parser in CI.

---

## 📦 Installation

### Supported platforms

| Platform | Standalone binary | Python package (`zotero-command-line`) |
| :--- | :--- | :--- |
| Linux x86_64, glibc 2.34+ (RHEL 9/AlmaLinux 9, Ubuntu 22.04, Debian 12, Fedora 36 or newer) | ✅ `.tar.gz`, `.deb`, `.rpm`, Docker | ✅ Python 3.11–3.14 |
| Linux x86_64 or ARM64, older glibc (2.17+) | ❌ | ✅ Python 3.11–3.13; 3.14 needs glibc 2.28+ |
| Linux with musl (Alpine) | ❌ | ✅ Python 3.11–3.14 |
| Windows x64 | ✅ `.msi`, `.zip` | ✅ Python 3.11–3.14 |
| macOS (Apple Silicon and Intel) | ❌ | ✅ Python 3.11–3.14, via `uv tool install` or `pipx` |

CI checks that the Python package installs from pre-built wheels on each of these platforms. Other platforms may work but aren't tested.

The release workflow also runs the built Linux binary (`--help`, `system selftest`, and offline commands against a fixture library) inside containers for each of the distros named above, so the glibc floor is checked on every release, not just claimed (Issue #413). The Windows binaries are unsigned: expect a SmartScreen "unknown publisher" warning and possible antivirus false positives on first run; `gh attestation verify <file> -R fchicout/zotero-cli` (see above) is the way to confirm a download is genuinely from this repository's release workflow without relying on code signing.

### Option 1: Standalone binaries (recommended)
Download a pre-built binary for your system. **You don't need Python.**

*   **Windows:** `.msi` installer or `.zip` from [Latest Releases](https://github.com/fchicout/zotero-cli/releases/latest).
*   **Linux (Ubuntu/Debian):** `.deb` package.
*   **Linux (Fedora/RHEL):** `.rpm` package.
*   **Any Linux:** `zotero-cli-linux-amd64.tar.gz`.

Or use the one-line installer scripts. They fetch the latest release (or the one named in `ZOTERO_CLI_VERSION`, e.g. `v3.0.5`) and check it against the release's `SHA256SUMS` before installing:
```bash
# Linux (x86_64, glibc 2.35+; on other systems it prints the PyPI command instead)
curl -fsSL https://raw.githubusercontent.com/fchicout/zotero-cli/main/install.sh | bash
```
```powershell
# Windows (PowerShell)
irm https://raw.githubusercontent.com/fchicout/zotero-cli/main/install.ps1 | iex
```

**Verifying a download yourself:** every release from v2.8.12 on includes a `SHA256SUMS` file and signed build provenance. With the [GitHub CLI](https://cli.github.com/), `gh attestation verify zotero-cli-linux-amd64.tar.gz -R fchicout/zotero-cli` confirms the file was built by this repository's release workflow.

**Binaries don't bundle the `rag` extra** (local/HF embeddings, `torch`, `sentence-transformers`): that stack is large and most installs never touch it. `rag` commands print a clear error in the binary; install from PyPI with `pip install 'zotero-command-line[rag]'` (or `uv tool install 'zotero-command-line[rag]'`) for those. Everything else, including offline mode and Markdown/PDF text export, works the same in the binary and from PyPI.

### 🐍 Option 2: From PyPI (Python 3.11+) - recommended on macOS
The package is called **`zotero-command-line`** on PyPI, because the `zotero-cli` name there belongs to an older, unrelated project. The command it installs is still `zotero-cli`. This is the way to install on macOS, Alpine, ARM Linux and older Linux systems, where there is no binary. [uv](https://docs.astral.sh/uv/) can install a suitable Python for you.

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

# Configure with an env file (ZOTERO_API_KEY=..., ZOTERO_LIBRARY_ID=...,
# ZOTERO_LIBRARY_TYPE=user or group, one per line),
# which keeps keys out of your shell history...
docker run --rm --env-file zotero.env zotero-cli system info

# ...or mount your existing config directory, running as yourself so any
# files zotero-cli writes there (logs, job state) belong to you
docker run --rm --user "$(id -u):$(id -g)" \
  -v ~/.config/zotero-cli:/config/zotero-cli zotero-cli system info
```

The container runs as an unprivileged user and keeps its config in `/config/zotero-cli`. That directory belongs to the image's own user, so with `--user` you must mount a directory you own there (as above); otherwise commands that keep state, such as `system jobs`, stop with an error saying so. On SELinux hosts (Fedora, RHEL), add `:z` to the mount: `-v ~/.config/zotero-cli:/config/zotero-cli:z`.

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

### ⬆️ Upgrading and uninstalling
Upgrading keeps your configuration (`~/.config/zotero-cli`, or `%APPDATA%\zotero-cli` on Windows); uninstalling leaves it too, so delete that directory as well if you want no trace. Read the [CHANGELOG](CHANGELOG.md) before a major upgrade.

| Installed with | Upgrade | Uninstall |
|---|---|---|
| `install.sh` | run it again (or set `ZOTERO_CLI_VERSION=3.0.5` for a given version) | `rm ~/.local/bin/zotero-cli` |
| `install.ps1` | run it again | delete `%LOCALAPPDATA%\zotero-cli\zotero-cli.exe` |
| `.msi` | install the newer `.msi`; it replaces the old one | Settings → Apps → *zotero-cli* → Uninstall |
| `.deb` | `sudo apt install ./zotero-cli_<version>_amd64.deb` | `sudo apt remove zotero-cli` |
| `.rpm` | `sudo dnf install ./zotero-cli-<version>.x86_64.rpm` | `sudo dnf remove zotero-cli` |
| `.tar.gz` / `.zip` | replace the `zotero-cli` binary | delete the binary |
| uv | `uv tool upgrade zotero-command-line` | `uv tool uninstall zotero-command-line` |
| pipx | `pipx upgrade zotero-command-line` | `pipx uninstall zotero-command-line` |
| Docker | `git pull` and `docker build -t zotero-cli .` again | `docker rmi zotero-cli` |

**Installed from git before 2.8.12?** That package was named `zotero-cli`, and pip treats `zotero-command-line` as a different package, so both can end up installed and fight over the `zotero-cli` command. Remove the old one first: `pip uninstall zotero-cli`.

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

`uv sync` creates `.venv/`, using the Python version pinned in `.python-version`, and installs the project in editable mode from `uv.lock`. Commit `uv.lock` alongside any dependency change so everyone, CI included, gets exactly the same versions. `pre-commit install` sets up the checks: ruff (lint and format), mypy and bandit run on every `git commit`, and `pytest tests/unit` runs on `git push`. See `.pre-commit-config.yaml`.

Read [CONTRIBUTING.md](https://github.com/fchicout/zotero-cli/blob/main/CONTRIBUTING.md) before opening a pull request: it lists the checks, the test layout, the rule for commands that delete, and how releases work. Everyone taking part follows the [Code of Conduct](https://github.com/fchicout/zotero-cli/blob/main/CODE_OF_CONDUCT.md).

### Getting help
Questions about using zotero-cli: [open an issue](https://github.com/fchicout/zotero-cli/issues/new/choose) with the **Question** form. Bugs and feature ideas use their own forms there too. This is a volunteer-run project, so replies can take a few days. Security problems go through [SECURITY.md](https://github.com/fchicout/zotero-cli/blob/main/SECURITY.md), never a public issue.

## Data Sources
Besides your Zotero library, zotero-cli queries public scholarly services (Crossref, Semantic Scholar, OpenAlex, Unpaywall, arXiv, PubMed and others) and identifies itself honestly when it does. [docs/DATA_SOURCES.md](https://github.com/fchicout/zotero-cli/blob/main/docs/DATA_SOURCES.md) lists them, links their terms, and explains attribution: if you publish results from `slr snowball`, credit Semantic Scholar. zotero-cli is an independent project, not affiliated with or endorsed by Zotero, the Corporation for Digital Scholarship, arXiv or any of these providers.

## Exit codes
Errors are one `Error: …` line on stderr, and the exit code says what kind of failure it was (usage, not found, authentication, network, …): see [docs/EXIT_CODES.md](https://github.com/fchicout/zotero-cli/blob/main/docs/EXIT_CODES.md).

## Versioning
zotero-cli follows Semantic Versioning from 3.0.0 on. [docs/COMPATIBILITY.md](https://github.com/fchicout/zotero-cli/blob/main/docs/COMPATIBILITY.md) lists what counts as the public interface (commands, flags, safety defaults, JSON/CSV output, config keys, stored formats) and how deprecations work. Upgrading from 2.x: see "Upgrading to 3.0" in the [CHANGELOG](https://github.com/fchicout/zotero-cli/blob/main/CHANGELOG.md).

## Security
To report a vulnerability, see [SECURITY.md](https://github.com/fchicout/zotero-cli/blob/main/SECURITY.md). Please don't use public issues for security problems.

## License
MIT License. See [LICENSE](https://github.com/fchicout/zotero-cli/blob/main/LICENSE) for details.
