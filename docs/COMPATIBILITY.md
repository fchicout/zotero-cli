# Versioning and Compatibility

zotero-cli follows [Semantic Versioning 2.0](https://semver.org/) from **3.0.0** on. This page says what that covers: which parts of the program you can build scripts, agents and pipelines on, and what counts as a breaking change.

In short: a **major** release (4.0.0) may break the public surface below, a **minor** release (3.1.0) only adds to it, and a **patch** release (3.0.1) only fixes bugs.

## The public surface

A change to any of these is a breaking change and waits for the next major release:

| Area | What is covered |
| :--- | :--- |
| Commands and options | Command, verb and flag names, and what arguments they take. |
| Safety defaults | Whether a command writes or only previews by default. A command that previews until `--execute` keeps doing so. |
| Machine-readable output | Field names and value types in `--format json` and `--format csv` output, and in JSON reports. New fields may appear in a minor release; consumers should ignore fields they don't know. |
| Configuration | `config.toml` keys, and the `ZOTERO_*` and provider environment variables. |
| Data written to your library | SDB decision notes (`sdb_version`, currently 1.2). |
| Files written to disk | `.zaf` backup archives (manifest `format: zaf`, `version` 1.1), `slr report snapshot` JSON (`schema_version` 1.0), and the background job database (`jobs.sqlite`). |

### Formats that carry a version

- **Readers keep accepting every older version.** A 3.x release reads SDB notes, `.zaf` archives and snapshots written by any earlier version, forever.
- **A new minor format version only adds fields.** Readers ignore fields they don't know.
- **An unknown major format version is refused** with a clear error, never silently misread. *Not enforced yet: the readers don't check versions today ([#455](https://github.com/fchicout/zotero-cli/issues/455)).*
- `jobs.sqlite` only migrates forward, with additive changes.

## Not covered

These can change in any release:

- Table layouts, colours, progress bars and other human-oriented output (use `--format json` or `csv` in scripts).
- The wording of messages, warnings and errors.
- The log file's format and location.
- Importing `zotero_cli` modules from Python. Only the command line is a public interface.
- **Exit codes**, until [#368](https://github.com/fchicout/zotero-cli/issues/368) makes them consistent. Today some failures still exit with status 0. Once #368 is fixed, exit codes join the public surface in a minor release.
- **The `rag` commands** (the optional `rag` extra), which are experimental. Their future is being decided in [#414](https://github.com/fchicout/zotero-cli/issues/414).
- `slr snowball`'s discovery-graph file, until it carries a format version ([#410](https://github.com/fchicout/zotero-cli/issues/410)).

## Deprecation

Before something public is removed or changed incompatibly:

1. It keeps working for **at least one minor release** and prints a deprecation warning to stderr naming the replacement (for example, `slr load --force` now warns and points to `--execute`).
2. The CHANGELOG lists it under **Deprecated** in the release that starts the warning.
3. It is removed or changed only in the **next major release**, listed under **Removed** or **Changed** with a one-line migration.

## Python and platforms

- **Minimum Python version:** raised only in a **minor** release, and announced one minor release ahead. zotero-cli currently supports Python 3.11 to 3.14.
- **Supported platforms:** listed in the [README](../README.md#supported-platforms). Dropping one is announced like a deprecation.

## Releases before 3.0

Versions up to 2.8.x did not follow this policy: several 2.x releases changed behaviour, including defaults that decide whether a command writes. The [CHANGELOG](../CHANGELOG.md) section "Upgrading to 3.0" lists every change a script written for 2.x needs.
