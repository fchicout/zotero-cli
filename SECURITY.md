# Security Policy

## Supported versions

Security fixes go into the latest release only. Please upgrade to the [latest release](https://github.com/fchicout/zotero-cli/releases/latest) before reporting, and check whether the problem still occurs.

| Version | Supported |
| ------- | --------- |
| Latest release | ✅ |
| Anything older | ❌ |

## Reporting a vulnerability

**Please don't open a public issue for security problems.**

Report them privately through GitHub: go to the repository's **Security** tab and click **[Report a vulnerability](https://github.com/fchicout/zotero-cli/security/advisories/new)**. Only the maintainers can see what you send.

Useful things to include:
- the zotero-cli version (`zotero-cli system info`) and your operating system;
- the command you ran and what happened;
- steps or a proof of concept to reproduce it;
- what an attacker could achieve.

**Remove your credentials first.** zotero-cli handles API keys for Zotero and several other services. Before attaching config files, logs or terminal output, replace every key and token with a placeholder. Logs are written to `~/.config/zotero-cli/logs/` on Linux/macOS and `%APPDATA%\zotero-cli\logs\` on Windows.

## What to expect

This is a volunteer-maintained project, so response times are best effort. We aim to:
- acknowledge your report within **7 days**;
- tell you whether we can reproduce it, and how serious we think it is;
- keep you updated while we work on a fix, and agree on a disclosure date with you.

Fixes ship in a new release with a GitHub Security Advisory. We credit reporters in the advisory unless you'd rather stay anonymous.

## Scope

In scope: the `zotero-cli` code in this repository, its release binaries and installers (`install.sh`, `install.ps1`, `.deb`, `.rpm`, `.msi`), and the published Python package.

Some things behave this way by design:
- **`zotero-cli serve`** is a local, single-user API for scripts on your own machine. It isn't meant to be exposed to a network. Problems that only occur after deliberately exposing it are still worth reporting, but they're lower priority.
- **Anyone with write access to a shared Zotero group library** can change the items everyone else sees. zotero-cli treats item data (titles, URLs, notes, attachments) as untrusted. A way to turn that data into code execution, credential leaks or file access outside zotero-cli's own directories **is** in scope.
- Vulnerabilities in Zotero itself, or in the external metadata services zotero-cli calls, should go to those projects.
