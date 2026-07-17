# Archive: Retired Process Documents

The files in this directory were produced by an earlier, Gemini-driven persona
workflow ("The Council of Six" — Pythias, Valerius, Argentis, Gandalf, Sullivan,
Vitruvius — plus Dr. Silas as scientific advisor, defined in `GEMINI.md`). They
are kept for historical record only and are **not authoritative**.

## Why they were retired

By 2026-07, these documents had drifted from reality and were actively
misleading: `VALERIUS_AUDIT.md` and the three `ARCHITECTURAL_ALERT_*.md` files
(all dated 2026-04-25) declared the project `REJECTED` / "Release is forbidden"
with failing tests and 100+ lint errors, while a live run of `ruff check .`,
`mypy .`, and `pytest tests/unit` the same week showed 0 lint errors, 0 type
errors, and 769/769 tests passing on merged v2.8.0. `ROADMAP.md` still listed
`v2.6.0` as the "Active Release" two versions behind reality, and
`v2.8.0_IMPLEMENTATION_PLAN.md` had every checkbox unchecked despite most of
the described reorg having already landed in the code.

The underlying problem: these were hand-narrated status claims, not derived
from anything verifiable, so they could (and did) silently drift out of sync
with the actual repository state.

## What replaced them

- **Live tool output** (`ruff check .`, `mypy .`, `pytest`) is the only source
  of truth for pass/fail/coverage status — never a hand-written verdict.
- **GitHub Issues** (`gh issue list --state open`, with the existing
  `type:`/`prio:`/`comp:` label taxonomy) is the source of truth for backlog
  and roadmap, not a hand-maintained markdown file.
- **`CLAUDE.md`** at the repo root carries current architectural/process
  guidance for AI agents working in this repo.
- **`docs/PROCESS.md`** still describes the development workflow (branching,
  the quality gate, release steps); read that alongside `CLAUDE.md`.

## What's in here

| File | Was |
| :--- | :--- |
| `GEMINI.md` | Persona definitions, team activation protocol, and session-history log for the Gemini workflow. |
| `ROADMAP.md` | Hand-maintained release roadmap, superseded by GitHub Issues/Milestones. |
| `VALERIUS_AUDIT.md` | A point-in-time (2026-04-25) quality-gate audit snapshot; stale by design — audits are transient, not living docs. |
| `v2.8.0_IMPLEMENTATION_PLAN.md` | The v2.8.0 reorg blueprint; largely implemented, but the checklist itself was never kept in sync with that. |
| `gemini_security/ARCHITECTURAL_ALERT_*.md` | Persona-raised architecture/quality risk reports, all dated 2026-04-25, already resolved by the time of archiving. |
| `communication/DEV_INBOX.md`, `communication/QUALITY_INBOX.md` | Persona-to-persona handoff logs for specific past feature batches. |

This repo's separate, unrelated `~/wks/gem-ctx` project (a shared cross-project
memory/vault used by the Gemini persona system) was left untouched — it may
still be load-bearing for other projects and is out of scope here.
