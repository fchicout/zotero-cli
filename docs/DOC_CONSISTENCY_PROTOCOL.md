# Documentation-Consistency Protocol

Formalized in Issue #147, prompted by a real bug the protocol's own first pass caught: `collection purge` was fully documented (`docs/commands/collection.md`, a working example) and backed by a real, already-implemented service method, but `collection_cmd.py::register_args()` never added a `purge` subparser — argparse rejected the documented command before `execute()` was ever reached (fixed in Issue #146). `tests/docs/test_doc_consistency.py` catches *structural* drift (every registered verb/flag has a doc entry, no orphaned doc files) but not *reachability* (a verb/flag can be textually present in both code and docs while unreachable) or *prose accuracy* (a description matching the old behavior, not the current one). This protocol exists to catch what the automated check can't, on a repeatable cadence rather than by memory.

## Prerequisite: the automated check must actually run

`pytest tests/docs` only exercises real checks if `zotero_cli.cli.main` (or any module that imports it) has already been imported in the same Python process — every CLI command self-registers via a `@CommandRegistry.register` decorator on its own module, which only executes once that module is imported. Before Issue #147, `test_doc_consistency.py` imported `CommandRegistry` directly but never `cli.main`, so `CommandRegistry.get_commands()` was silently empty whenever `pytest tests/docs` ran in isolation (exactly how this protocol's own step 1 instructs). Five of the eight tests in that file walk the registry and so passed vacuously — checking nothing — while the two `*_no_orphans` tests failed loudly, because they check the other direction (docs → registry) where real files on disk make an empty registry visible instead of silent. `test_doc_consistency.py` now imports `zotero_cli.cli.main` directly, so this can't recur silently — but if a similar test file is ever added elsewhere, apply the same check: does it actually import what it needs to observe, or could an empty/unregistered state pass by accident?

## The protocol

**Step 1 — Generate the ground-truth tree from source, never from docs.**
Walk `CommandRegistry.get_commands()` and each command's `register_args()` directly (the exact mechanism `test_doc_consistency.py::get_all_cli_command_paths()` uses) to produce the full noun → verb → sub-verb → parameter tree. Docs are what's being audited, so they can't be the starting point. A rendered version of this tree (noun/verb diagram + full parameter matrix) should exist as an up-to-date artifact before starting a sweep — regenerate it, don't reuse a stale one.

**Step 2 — Walk the tree one leaf at a time. For each leaf, and its parent node, check three layers against three kinds of consistency.**

Layers:
- `docs/help_specs/<file>.md` — the detailed DOC-SPEC (7-section template).
- `docs/commands/<noun>.md` — the per-noun reference doc.
- `README.md` — command index table, Cookbook examples, workflow diagrams, any prose mention.
- **The parent node's own help text**, not just the leaf's — a noun's top-level `--help` description/epilog can drift independently of its verbs' docs; don't assume parent correctness follows from child correctness.

Checks, cheapest to most expensive:
1. **Structural** (automated — `pytest tests/docs`, see prerequisite above): every verb/flag has a doc entry; no doc file describes a noun/verb that no longer exists. Run this first, as a filter, before manual review.
2. **Reachability** (not automated): actually run or argparse-dry-validate every documented example command. Presence-checking doesn't execute anything — this is what caught `collection purge`.
3. **Semantic/prose accuracy** (not automated): does the description match current behavior, not just current flag names? A stale description can point at the wrong replacement command even when every flag it mentions still exists.

**Step 3 — Record findings before fixing.** One row per leaf command (path / help_specs status / commands status / README status / notes), so the sweep is auditable and fixes land as a reviewable PR per `docs/PROCESS.md`, not one undifferentiated diff.

**Step 4 — Fix, then close the loop.** Re-run `pytest tests/docs` and regenerate the tree to confirm zero structural drift remains. Steps 2 and 3's reachability/prose checks have no automated regression coverage yet (see Future Work) — re-run them by hand for anything touched.

## When to run this

- Before cutting a release that bundled multiple CLI-facing changes (new verbs, changed flags, renamed commands).
- Whenever a `docs/commands/*.md` or `docs/help_specs/*.md` file is touched by hand outside a normal single-issue PR (e.g. a batch cleanup).
- As a periodic full sweep — no fixed cadence mandated; use judgment based on how much CLI surface has moved since the last one.

Per-issue PRs that touch CLI args are expected to keep their own slice of the tree in sync as part of normal `docs/PROCESS.md` Phase D ("Documentation Sync") — this protocol is for the deliberate, whole-tree sweep, not a substitute for keeping docs current PR-by-PR.

## Future work (not yet built)

- Script the tree generation (`scripts/generate_command_tree.py`, matching the convention of `scripts/generate_badges.py`) so step 1 stops being manual.
- An automated reachability check: for every documented example command, argparse-parse it against the real parser tree (no execution) and assert it doesn't raise `SystemExit`/`invalid choice` — would have caught `collection purge` mechanically instead of by hand.

## Related

- #143, #144 — prior doc-consistency sweeps this protocol formalizes and extends.
- #146 — the `collection purge` dead-code bug that motivated writing this protocol down.
- #140 — a separate pre-existing gap (`get_trash_items` missing from the `ZoteroGateway` Protocol) that a full tree-walk would also have flagged.
