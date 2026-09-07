# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### 🛡️ Quality & Infrastructure
- **Hardening: `x-api-key` header retained across cross-origin redirects in `NetworkGateway` (Issue #241):** `httpx`'s built-in redirect handling strips `Authorization` on a cross-origin hop, but `NetworkGateway` follows redirects manually (Issue #235's SSRF re-validation) and was reusing the original request's headers - including non-standard auth headers like Semantic Scholar's `x-api-key` - unconditionally on every hop, regardless of origin. Not currently exploitable purely from Zotero library or API response data (both audit passes confirmed this requires the fixed, hardcoded `api.semanticscholar.org` target to itself issue a cross-origin redirect - infrastructure compromise or a MITM, not attacker-triggerable input), but a real defense-in-depth gap. `_fetch_validated` now compares each redirect hop's origin (scheme/host/port) against the previous hop's, stripping `Authorization`/`x-api-key` (case-insensitively) from the headers carried forward whenever they differ - mirroring what `httpx` already does for `Authorization`, extended to this codebase's actual non-standard auth header. Found via the adversarial two-agent security audit tracked in #231.

### 🐛 Bug Fixes
- **Predictable shared-tmp-dir filenames across the PDF-resolver family (Issue #240):** Every PDF resolver (`unpaywall.py`, `semantic_scholar.py`, `arxiv.py`, `generic_scraper.py`, `openalex.py`, `bdtd.py`), `zotero_api.py`'s thesis-import PDF fetch, and `sqlite_repo.py`'s offline-mode shadow-copy path all built their temp-file path by manually joining `tempfile.gettempdir()` with a fully deterministic filename (`f"unpaywall_{item.key}.pdf"`, `f"zotero_cli_shadow_{os.getpid()}.sqlite"`, etc.) instead of using `tempfile.mkstemp()` (already used correctly elsewhere, e.g. `restore_service.py`, `attachment_service.py`). On a shared multi-user host with a world-writable `/tmp`, a local attacker could pre-create a symlink at that guessable path - item keys are visible to any library collaborator, and PID space is bounded/reused - causing the write to follow the symlink and overwrite an arbitrary victim-owned file. New shared `core/utils/safe_tempfile.py` (`write_secure_temp_file()`) wraps `tempfile.mkstemp()` (which creates the file itself, `O_CREAT|O_EXCL`, mode `0600` - nothing for an attacker to have pre-planted) and is now used at all 6 resolver sites; `zotero_api.py` and `sqlite_repo.py` call `tempfile.mkstemp()` directly since they stream/copy into the file descriptor rather than writing a single `bytes` payload. Found via the adversarial two-agent security audit tracked in #231 (principal found 3 instances, the critic pass found 5 more identical ones).
- **Unbounded response body reads on every PDF-download code path (Issue #239):** Neither `requests` nor `httpx` caps response body size by default, and every PDF-fetch code path in the resolver chain (every `core/services/resolvers/*.py` PDF resolver via `NetworkGateway`, `attachment_service.py`'s existing-URL check, and `zotero_api.py`'s thesis-import PDF fetch) either buffered the whole body into memory or streamed it to disk with no cap - a malicious/compromised metadata source, or (combined with #235's SSRF finding) an attacker-controlled `item.url`, could serve an arbitrarily large or slow-drip response and exhaust memory or disk on the machine running `item pdf fetch`/`item attach-pdfs`. `core/utils/url_safety.py` now enforces a shared 50MB `MAX_RESPONSE_BYTES` cap via an upfront `Content-Length` pre-check plus a hard streaming cutoff that also catches a server lying about or omitting that header: `iter_capped_content()` wraps the sync (`requests`) streaming path used by `attachment_service.py`/`zotero_api.py`, and `read_capped_async()` wraps the async (`httpx`) path, now used internally by both `safe_async_get()` (switched from `client.get()` to `client.send(..., stream=True)` so the cap can actually abort mid-download rather than after the fact) and `NetworkGateway._fetch_validated` (same `build_request`/`send(stream=True)` switch), covering every resolver that routes through the gateway for free. A response that trips the cap raises `ResponseTooLargeError`; the two sync download sites also now clean up their partially-written temp file on any failure (previously only handled on a successful-but-non-PDF response), closing a related disk-leak this cap would otherwise still leave behind. Found via the adversarial two-agent security audit tracked in #231.
- **Zip-slip via attachment filename in `.zaf` backup archives (Issue #238):** `BackupService._download_attachment_file` built the zip entry's arcname as `f"attachments/{p_key}/{filename}"` using `filename = data.get("filename") or data.get("title")` — Zotero attachment metadata settable by any collaborator with write access to a shared library — with no sanitization. A crafted filename containing `../` path-traversal segments (e.g. `"../../../../etc/passwd"`) could place the written entry outside the intended `attachments/<parent>/` directory inside the archive. Now sanitized via `os.path.basename()` before use, with a fallback to the item's own key when that sanitizes down to an empty or dot-only result (e.g. a filename of just `..`). `RestoreService`'s corresponding read path was independently confirmed already safe by both audit agents (it uses `zf.read()` on named manifest entries, never `zipfile.extractall()`), so no read-side change was needed. Found via the adversarial two-agent security audit tracked in #231.
- **CSV export enables spreadsheet formula injection (Issue #237):** Every CSV-writing code path in the project (`report_cmd.py`'s duplicate-report export, `slr list qa-approved --csv`, `extraction_service.py`'s synthesis-matrix export, `sync_service.py`'s screening-state recovery, `merge_plan_io.py`'s merge-plan export, `screening_state.py`, and `canonical_csv_lib.py`) wrote Zotero item fields (title, abstract, etc. - settable by any collaborator with write access to a shared library) directly into cells with no sanitization, enabling CSV/spreadsheet formula injection (e.g. `=HYPERLINK(...)`) when a reviewer opens the export in Excel/LibreOffice/Google Sheets. New shared `core/utils/csv_safety.py` (`sanitize_csv_cell`/`sanitize_csv_row`/`sanitize_csv_rows`) prefixes any cell value starting with `=`, `+`, `-`, `@`, tab, or CR with a leading `'`, per OWASP's recommended mitigation, applied at all 7 confirmed writer sites. Since `canonical_csv_lib.py`'s format is both written *and re-read* by this project (`system normalize`), also added `unsanitize_csv_cell()` on its read path so re-importing a file this project itself exported doesn't treat the escape marker as literal data.
- **Credential-bearing config.toml written world-readable (Issue #236):** `config.toml` holds live API keys/tokens (Zotero, OpenAI, Gemini, Hugging Face, Semantic Scholar, CORE, NCBI) but was written with a plain `open(path, "w")`, inheriting the process's default umask - empirically confirmed to leave it `0644` (world-readable) on a real config file. Any other local user on a shared multi-user machine could read every credential this tool has stored. New shared `secure_config_open()` helper (`core/config.py`) opens the file via `os.open` with an explicit `0600` mode set at creation, creates the parent directory `0700`, and `chmod`s the file descriptor too (the `os.open` mode argument is silently ignored for a *pre-existing* file, so a config written by an older version of zotero-cli gets its permissions tightened the next time it's updated, not left insecure). Applied to both write sites: `ConfigManager.update_config` (used by `system switch`/other config-mutation flows) and `init_cmd.py`'s first-run config-creation wizard.
- **SSRF + exfiltration via unvalidated URL fetch across every PDF-resolver code path (Issue #235):** Every PDF-acquisition path reachable from `item pdf fetch`/`item attach-pdfs` (`attachment_service.py`'s existing-URL check, every `core/services/resolvers/*.py` PDF resolver, and `zotero_api.py`'s thesis-import PDF fetch) fetched an externally-influenceable URL — `item.url` (attacker-settable by any collaborator with write access to a shared library) or a third-party API's `pdf_url` — with no scheme/IP validation, then uploaded the response back onto the Zotero item as an attachment, readable by that same collaborator. New shared `core/utils/url_safety.py` (`validate_public_url`/`safe_get`/`safe_async_get`) rejects non-`http(s)` schemes and any hostname resolving to a loopback/private/link-local/multicast/reserved address, re-validated on *every* redirect hop rather than trusting `requests`/`httpx`'s default redirect-following (a validated public URL could otherwise still redirect into an internal address). `NetworkGateway` (used by `bdtd.py`/`generic_scraper.py`/`unpaywall.py`/`semantic_scholar.py`/`arxiv.py`'s resolvers) now routes every request through this guard centrally; `attachment_service.py`, `zotero_api.py`'s thesis path, and `openalex.py`'s standalone httpx client were updated individually since they don't share the gateway. Also added a `%PDF` magic-byte check before upload at every site that lacked one (`attachment_service.py`, `openalex.py`, `zotero_api.py`), checked on the first streamed chunk rather than re-reading the file afterward. Found via the adversarial two-agent security audit tracked in #231.

## [2.8.8] - 2026-09-07

### 🐛 Bug Fixes
- **`SnowballGraphService` had no per-library storage scoping (Issue #228):** Every other stateful snowballing service already supports it - `JobQueueService` filters by `library_id` (Issue #150), and `get_snowball_worker`/`get_snowball_ingestion_service` both accept an optional `ZoteroConfig` - but `get_snowball_graph_service()` took no config at all and always resolved to one process-global `discovery_graph.json`. Any two callers targeting different Zotero libraries (a multi-tenant caller running one discovery graph per research project, or even a single CLI user who `system switch`ed between groups mid-session) would silently read/write the identical file, corrupting each other's candidate graphs. `get_snowball_graph_service` now accepts an optional `config: Optional[ZoteroConfig]`, resolving to `discovery_graph_{library_id}.json` when one is supplied (falling back to `user_id`, then `"default"`) and the pre-#228 global path when it isn't - `get_snowball_worker`/`get_snowball_ingestion_service` now thread their own resolved config through, and `SnowballCommand` resolves one config per CLI invocation and passes it to every snowball-graph call site (seed/discovery/review/import/status/export), so the whole CLI is consistently scoped too, not just multi-tenant callers. A pre-existing global `discovery_graph.json` is migrated (renamed, not just pointed at) into the first library that touches it after upgrading, so existing local state isn't silently orphaned.

## [2.8.7] - 2026-09-07

### ✨ Features & Improvements
- **Snowball review flags candidates already present in the library (Issue #224):** Library membership was only ever checked at import time (`SnowballIngestionService._is_duplicate`) - a researcher reviewing candidates had no way to know some were papers they already had until after accept + import, when the item was silently skipped with just a lower "N imported" count than "N accepted". `SnowballReviewTUI` now builds a normalized-DOI -> Zotero-key index in one batched `get_all_items()` pass at the start of a review session (reusing the same `normalize_doi()`-based matching #205 introduced, so a bare-DOI candidate still matches a library item stored in URL-form), and flags each candidate's metrics panel with `⚠ Already in library (KEY)` instead of presenting it identically to a genuinely new candidate. Optional (`gateway` param defaults to `None`) so a caller without one still gets a working, just un-annotated, review session. Export (`--format json`/`mermaid`) intentionally left untouched per the issue's own scoping - not urgent, a natural follow-on.

### 🐛 Bug Fixes
- **Forward snowballing 403s and fails outright whenever `semantic_scholar_api_key` is configured (Issue #223):** Confirmed live against the real Semantic Scholar API: a configured key can be rejected (403) across every S2 endpoint while the identical unauthenticated request succeeds - `NetworkGateway`'s existing 403 handling (rotate identity, retry once) can never fix a bad credential, so it just surfaced a raw `httpx.HTTPStatusError`/traceback for what's really a rejected-key condition. `NetworkGateway._execute_request` now recognizes this case (a 403 that survives identity rotation *with* an API-key/auth header present) and raises a clear, actionable `ValueError` instead. `SnowballDiscoveryWorker._discover_forward` catches that specifically and falls back to a single unauthenticated retry rather than failing the whole job - turning a hard failure (0 candidates, every time a key is configured) into degraded-but-working behavior, with a logged warning. Also added the proactive `time.sleep`-equivalent pacing (`asyncio.sleep(1.1)`, matching `infra/semantic_scholar_api.py`'s own existing 1-req/sec self-throttle) that forward discovery never had - the only backoff that existed before was reactive (per-job, only after a 429 already happened), which isn't enough to avoid tripping Semantic Scholar's low, globally-shared unauthenticated pool once the fallback path is exercised.

## [2.8.6] - 2026-09-07

### 🐛 Bug Fixes
- **Reopened Issue #205 - `get_items_by_doi` structurally cannot find matches via Zotero's search API:** The v2.8.5 fix normalized DOI *format* in the comparison, but Corbenic-SLR's re-test (verified directly against the live Zotero Web API, not just this codebase) found `_is_duplicate` still couldn't detect any duplicate: `get_items_by_doi` relies on `search_items(ZoteroQuery(q=doi))`, and Zotero's `q`/`qmode` search does not index the structured DOI field under either `qmode` value (`titleCreatorYear` or `everything`) - it always returns zero results for a DOI-only query, regardless of format. `ZoteroAPIClient.get_items_by_doi` now does a client-side scan instead: paginate `get_all_items()` and filter locally with `normalize_doi()` - the only approach that actually works given this Zotero API limitation. This also transitively fixes the same structural gap in `RestoreService` and `search --doi`, both of which call the same shared `get_items_by_doi`. Offline mode (`SqliteZoteroGateway`) was never affected - it already queries the local DOI column directly via SQL.

## [2.8.5] - 2026-09-06

### ✨ Features & Improvements
- **Snowball accept/reject decisions now capture a reason and evidence depth (Issue #211):** `SnowballGraphService.update_status` recorded a bare status transition with no audit trail of *why* - inconsistent with this project's own SDB screening-decision pattern (`ScreeningService.record_decision`, which captures a criteria code alongside every include/exclude). `update_status` now accepts optional `reason: str` and `depth: Literal["title", "abstract", "full_text"]` params, storing them on the graph node as `decision_reason`/`decision_depth`; `SnowballReviewTUI` prompts for both after every accept/reject (depth defaults to `abstract`, reason is optional free text). Surfacing these in `get_stats()`/`to_mermaid()`/export is left as a natural follow-on now that they're captured, not done here.
- **Snowball review hydrates un-titled stub candidates before display (Issue #210):** `slr snowball review`'s candidates came straight off the graph as discovered — for backward/CrossRef candidates this is frequently just a generic `"Reference from {parent-doi}"` stub with no abstract (CrossRef reference lists very often omit `article-title`/`unstructured`), making an informed accept/reject decision impossible without looking the paper up externally. `SnowballReviewTUI` now calls the existing `MetadataAggregatorService.get_enriched_metadata(doi)` (already used by `SnowballIngestionService._hydrate_paper` at import time, just never wired into review) to backfill title/abstract/authors/year per-candidate as the TUI advances, whenever a candidate looks like an un-hydrated stub - and persists the title/abstract back onto the graph node so re-reviewing (or the later import) doesn't re-fetch the same metadata. Falls back to the un-hydrated view (no crash) if no metadata service is configured.
- **`slr snowball seed --dois`/`--from-accepted`: seed the next generation without an import round trip (Issue #206):** Wohlin's snowballing method is iterative (seed → discover → review → re-seed the next generation from this generation's accepted candidates → repeat), but `seed` previously only accepted `--keys`/`--collection`, both resolving *existing Zotero items* — a candidate accepted in generation N is only a graph node with a DOI, not yet a Zotero item, so there was no way to pass it back into `seed` for generation N+1 without importing every generation before starting the next one. Added `--dois` (comma-separated bare DOIs, skips the Zotero-item lookup entirely) and `--from-accepted [--from-generation N]` (reads the graph's own `ACCEPTED` nodes directly via a new `SnowballGraphService.get_accepted_dois()`, optionally scoped to one prior generation) — the latter is the "one-click next generation" flow closest to Wohlin's own guideline. `docs/help_specs/slr_snowball.md`'s parameter matrix and examples updated (and its pre-existing broken `--doi` example, which referenced a flag that never existed, corrected to the real `--dois`/`--keys` flags along the way).

### 🐛 Bug Fixes
- **`system info`'s Group URL could point at a stale, inactive group (Issue #209):** The "Group URL" line printed `config.target_group_url` verbatim, but that's a separately-stored config value only ever consulted as a fallback when `library_id` itself is unset (`ZoteroConfig.resolve_library_target`'s priority cascade) - once `library_id` is set, `target_group_url` is inert and unrelated to what's actually active. `system switch` updates `library_id`/`library_type` but never touches `target_group_url`, so after switching, `system info` could show a real, different group's URL right next to the correct numeric Library ID - exactly the mistake `system switch`'s own documented safety tip warns against (scan the more legible "Group URL" line, land on the wrong library). Now derives the Group URL directly from the same `library_id`/`library_type` already printed above it (`https://www.zotero.org/groups/{library_id}`), so drift between the two lines is no longer possible.
- **`slr snowball export --format json` produced no output at all (Issue #208):** `_handle_export`'s `json` branch was a literal `pass` - no output, no error, exit 0, on both an empty and a populated graph. Added `SnowballGraphService.to_json()` (reuses the same `nx.node_link_data` shape `save_graph()` already persists to disk, mirroring the existing `to_mermaid()`) and wired it into the `json` branch. While in there: switched the export print path to `markup=False`, since a real paper title or Mermaid node label routinely contains literal `[...]` that Rich's console markup parser would otherwise silently swallow as a (nonexistent) style tag, corrupting the printed JSON/Mermaid.
- **`ZoteroAPIClient.get_item` gave an opaque crash for a malformed/invalid item key (Issue #207):** `slr snowball seed --keys <bad-key>` (e.g. a bare DOI passed where a Zotero item key was expected) printed a raw `'list' object has no attribute 'get'` — a malformed key can route to an endpoint that returns a list instead of a single item object or a 404, and `ZoteroItem.from_raw_zotero_item` then crashed calling `.get()` on it. `get_item` now checks the response shape and fails with a clear `'<key>' is not a valid Zotero item key` message instead.
- **Snowball import created duplicate Zotero items for URL-form DOIs (Issue #205):** `SnowballIngestionService._is_duplicate` lowercased both sides of a DOI comparison but never normalized *format* — a bare DOI already in the library (`10.1109/tse.2026.3694876`) and a URL-form DOI a metadata provider hydrated for the same paper during a snowball import (`https://doi.org/10.1109/tse.2026.3694876`) compared as unequal, so the paper was silently re-imported as a brand-new duplicate item. Switched to the project's existing `normalize_doi` helper (`core/utils/normalization.py`, already used by `slr csv_inbound`'s DOI matching) on both sides of the comparison instead of a bespoke `.lower()`-only check.
- **Forward snowballing never discovered any candidates (Issue #204):** `SnowballDiscoveryWorker._discover_forward`'s Semantic Scholar `/citations` request omitted `externalIds` from its `fields` param, so every `citingPaper.externalIds.DOI` lookup came back empty and every single forward candidate was silently dropped — confirmed live: a seed with 20 real citations (17 with a DOI) added 0 nodes via `slr snowball discovery`, with the job still reporting `COMPLETED`. Added `externalIds` to the requested fields; no other Semantic Scholar call site in the codebase shares this gap (`infra/semantic_scholar_api.py` already requests it).

## [2.8.4] - 2026-09-05

### ✨ Features & Improvements
- **`ScreeningService.record_decision` split into composable primitives (Issue #201):** `record_decision` used to unconditionally write the persona's audit note *and* apply shared, item-level tags/collection-movement in one call — fine for solo screening, but wrong for double-blind screening: two independent raters calling it on the same item would each fire the shared tags/move, driven by whichever called last, even when they disagreed. Split into `record_decision_note` (note write/upsert only, safe to call per-persona with no shared side effects), `apply_decision_outcome` (tags + collection move only, meant to be called once a decision is *final* — immediately after a solo decision, or after a double-blind pair is reconciled), and `get_decisions_for_item` (returns every persona's parsed decision, so a caller can check who decided what without hand-rolling note scanning). `record_decision` itself stays as a thin, non-breaking wrapper (`record_decision_note` + `apply_decision_outcome` in sequence) — every existing solo-screening caller (CLI, TUI) is unaffected.
- **API clients for CORE, Semantic Scholar search/count, and DOAJ (Issue #190):** Three new/extended library-level metadata sources, following the exact `ArxivGateway`/`SearchableMetadataProvider` pattern already established, for a downstream consumer (Corbenic-SLR) building live "search + count + import" catalog pages: OpenAlex/PubMed/ERIC/INSPIRE-HEP already had clients, so no ask there.
  - **`CoreAPIClient`** (new, `infra/core_api.py`): CORE (core.ac.uk)'s open-access aggregator search API v3. Requires a free API key (`config.core_api_key`/`CORE_API_KEY` env var, registration at core.ac.uk/services/api; free tier is 3,000 req/month, 3 req/s) — deliberately *not* registered with `MetadataAggregatorService`'s always-on lookup fan-out, to avoid burning that budget on every single DOI lookup regardless of whether CORE results are wanted; reachable only via the new standalone `GatewayFactory.get_core_client()`.
  - **`SemanticScholarAPIClient.count(query)`** (new): the client already had `search()` (#179); adding `count()` closes the gap the issue called out — a result count without paginating full records, reading the same `total` field `search()` already uses.
  - **`DOAJAPIClient`** (new, `infra/doaj_api.py`): the Directory of Open Access Journals' search API, no API key required.
  - New shared `CountableMetadataProvider` interface (`core/interfaces.py`), mirroring `SearchableMetadataProvider`'s "optional capability mixin" shape — `count(query) -> int`, implemented by all three of the above.
  - `core/strategies.py`'s `BdtdImportStrategy` (added in #182) renamed to `SearchableProviderImportStrategy` and generalized: it always only depended on the shared `SearchableMetadataProvider.search()` shape, not anything BDTD-specific, so the same class now serves CORE/Semantic Scholar/DOAJ too without duplicating three near-identical wrapper classes.
  - Library-level only, per the issue's own framing (Corbenic builds its own "Import from CORE/Semantic Scholar/DOAJ" UI on top of these) — no new CLI verb in this change.
- **`import bdtd --query`: free-text bulk import from BDTD (Issue #182):** `import bdtd` previously only accepted a single BDTD record ID, repository handle URL, or DOI. `BDTDAPIClient` now additionally implements `SearchableMetadataProvider` (the same interface added for OpenAlex/Semantic Scholar in #179) via BDTD's VuFind search endpoint, and `import bdtd --query "<free text>" --collection ... --limit N` bulk-imports up to `N` matching theses/dissertations through a new `BdtdImportStrategy`. Bulk search results deliberately skip the synchronous per-record PDF-URL scraping `get_paper_metadata` normally does for a single identifier — scraping+HEAD-probing every landing page for up to `N` records would be far too slow for a search preview — deferring PDF resolution to the existing async `BDTDResolver`, run later via `item pdf fetch`/the normal job pipeline. Exactly one of `identifier`/`--query` must be given.
- **`ArxivGateway.count(query)` (Issue #181):** Returns the total result count for a query without fetching/discarding individual `ResearchPaper` objects — reads `<opensearch:totalResults>` straight off a single-item Atom feed page, the same total the `arxiv` package's own `Client._results()` already fetches internally as part of the first page (`feed.header.total_results`) but never surfaced through `ArxivGateway`'s public interface. Enables a read-only "About N results" exploratory-search UI (Corbenic-SLR's use case) that judges a candidate query's breadth before committing to a real import, without the bandwidth/rate-limit cost of a capped fetch-and-count stopgap.
- **RAG/AI dependencies split into an optional `[rag]` extra — "lite" install (Issue #180):** `torch`, `sentence-transformers`, `huggingface-hub`, `numpy`, `einops`, `accelerate`, `openai`, and `google-generativeai` moved out of the base `dependencies` into `[project.optional-dependencies].rag`. Measured impact for a consumer like Corbenic-SLR that only needs Zotero I/O/SLR/screening/extraction, not RAG: a Docker image pinned to `v2.8.3` was 11.5GB (CUDA `torch` wheel); this alone doesn't fix a wheel-index choice, but removing the whole RAG stack from a lite install's dependency tree is the bigger win the pinned-CPU-wheel workaround couldn't reach. Every import of these packages in `src/` was already function-local/lazy (verified by reading the code, not assumed) — so this was purely a `pyproject.toml` packaging change, not the dependency-injection rework flagged as a future concern when Issue #154 was decided; a lite-install consumer who does hit a RAG code path gets a clear `ImportError`, not a crash. `markitdown` (and its `onnxruntime` dependency) deliberately stayed in the base dependencies despite being large, since `item`/`collection export --format md` — a non-RAG feature — depends on it too; moving it would have broken that command for lite installs. `dev` now self-references `zotero-cli[rag]` so `uv sync --extra dev`/CI keep installing everything the full test suite needs, unchanged.
- **Free-text/topic search for OpenAlex and Semantic Scholar (Issue #179):** `OpenAlexAPIClient`/`SemanticScholarAPIClient` previously implemented only `get_paper_metadata(identifier)` — resolving an already-known DOI/arXiv-ID/S2-ID, with no way to search by topic the way `ArxivGateway.search` already allows. Both now additionally implement a new `SearchableMetadataProvider` interface (a separate, additionally-inherited mixin — not every one of this project's 11 metadata sources supports free-text search, so it isn't a `MetadataProvider` method) with a `search(query, max_results=100, sort_by="relevance", sort_order="descending") -> Iterator[ResearchPaper]` method mirroring `ArxivGateway.search`'s shape, transparently paginating each API's native page-size cap (200 for OpenAlex, 100 for Semantic Scholar) up to `max_results`. Neither requires an API key. Library-level only per the issue's own scoping — no new CLI verb in this change.
- **Library-independent API key identity resolution (Issue #178):** `ZoteroAPIClient.resolve_key_identity(api_key)` (new `@staticmethod`, no instance/`library_id` required) calls Zotero's `GET /keys/<api_key>` — the one REST endpoint that needs no library scope — and returns a typed `KeyIdentity(user_id, username, access)`. Closes a chicken-and-egg gap for any account-setup flow (Corbenic-SLR's included) that needs to validate a researcher's API key and discover their personal `userID` *before* any library/group is known. `zotero-cli init` now uses it too: the wizard resolves and confirms the key's identity immediately after it's entered, prefilling the Library ID prompt (user mode) and the personal User ID prompt (group mode) with the resolved `userID` instead of asking the user to go look it up separately; resolution failures degrade to the prior plain-prompt behavior rather than blocking setup.
- **`GET /jobs`/`GET /jobs/{id}` API routes (Issue #150):** `serve`'s FastAPI layer now exposes read-only background-job status (queued `fetch_pdf`/snowball-discovery jobs and their retry state), so an external consumer like Corbenic-SLR can poll job progress through the API instead of reading `jobs.sqlite` directly — closing the same "serve API only has collections/items" gap that blocked this and several other corbenic-facing features.
- **`item trash`/`item restore`, Zotero-Desktop-compatible (Issue #145, Phase 1):** New offline-only commands that move an item to/from the trash by writing directly to the local `zotero.sqlite`, replicating exactly what Zotero Desktop's own client writes (confirmed against Desktop's real source: `Zotero.Items.trash()`/`trashTx()` and `item.deleted = false; item.save()`) — bumps `dateModified`/`clientDateModified`, marks the row dirty (`synced=0`) so Desktop's next real sync pushes the change to the server, and adds/removes a `deletedItems` row. `version` is deliberately left untouched, matching Desktop (only the server bumps it on sync). This is the first write path ever added to the previously fully-read-only `SqliteZoteroGateway`; every other offline mutation still raises `Offline mode is read-only`. Preview-only by default (`--execute` required, confirmation prompt unless `--force`); rejected outright against an online/API gateway, which has no documented reversible trash write. Does not replicate Desktop's merge-relations cleanup on restore (stripping `dc:replaces` relations from a prior `item merge`) — narrow edge case, documented as a known limitation rather than guessed at. Phase 2 (online mode) is intentionally out of scope for this change.

### 🐛 Bug Fixes
- **`slr source list` no longer makes one Zotero API call per item (Issue #189):** `_handle_list` called `gateway.get_item_children(item.key)` once per item, purely to detect a PDF attachment and an SDB-note child — for a source with a few hundred items, a few hundred sequential `GET /items/<key>/children` round trips, making the command take minutes rather than seconds against the Zotero Cloud API. Replaced with two library-wide, paginated `search_items(ZoteroQuery(item_type=...))` scans (`attachment`, `note`) done once up front regardless of source/item count, building parent-key sets checked with an O(1) membership test per item instead of a network call. Extends the fix corbenic-slr already shipped for its own mirrored PDF-detection logic (which only handled the PDF side) to also cover the SDB-note check the same way, since both use the identical per-item pattern.
- **`item pdf attach`/`upload_attachment` reliably 428s (Issue #191):** `ZoteroApiClient.upload_attachment` failed at one of two steps against the real Zotero Web API, root-caused via direct diagnostic calls against a live library. Step 2 (upload authorization) sent both `If-None-Match: *` and `If-Unmodified-Since-Version` — Zotero 428s that combination, since there's no prior version of a just-created attachment to be "unmodified since"; removed the stale header (the comment above it citing #79 was a mislabeled leftover — #79 is unrelated CLI-parameter-naming work). Step 4 (registering the upload) was missing `If-None-Match: *` entirely, which Zotero also rejects with 428 (`"If-Match/If-None-Match header not provided"`); added it. A failure at either step also now cleans up the orphaned, empty attachment placeholder item created in step 1, instead of leaving it behind for the user to delete by hand.
- **`tests/docs` was silently vacuous when run in isolation (Issue #147):** `test_doc_consistency.py` imported `CommandRegistry` but never `zotero_cli.cli.main` — every CLI command only self-registers with `CommandRegistry` when its own module is imported, so `CommandRegistry.get_commands()` was empty whenever `pytest tests/docs` ran standalone (exactly how the project's own documentation-consistency protocol instructs it to be run). 5 of the 8 tests in that file walk the registry and so passed vacuously, checking nothing; only the 2 `*_no_orphans` tests (which check the opposite direction — docs → registry) failed, because real files on disk made the empty registry visible instead of silent. Fixed by importing `zotero_cli.cli.main` directly; all 8 tests now genuinely pass. Running the now-real reachability check by hand (per the new protocol below) also found and fixed 4 documented example commands (`item_trash.md`, `item_restore.md`, `docs/commands/item.md` ×2, plus the CLI's own `--help` epilogs for `item trash`/`item restore`) that put the global `--offline` flag *after* the subcommand — argparse rejects that with `unrecognized arguments: --offline`, since global flags must precede the subcommand. None of those examples were actually runnable as written.
- **Super-linear regex backtracking in `MarkdownRecursiveSplitter` (SonarQube `python:S8786`):** `rag_service.py`'s markdown-header regex used `\s+` (which also matches `\n`) directly against a `[^\r\n]*$` tail under `re.MULTILINE`, giving the engine an ambiguous boundary across newlines. Narrowed to `[ \t]+` — markdown headers never have a literal newline between the `#`s and the header text, so this isn't a behavior change, just removes the backtracking hazard. Found while investigating an unrelated CI quality-gate failure on PR #183; fixed here rather than filing a separate issue since it was the one thing blocking that gate.
- **`SqliteZoteroGateway`'s read path now matches real Zotero Desktop databases (Issue #174):** Offline mode's entire read surface (`search_items`, `get_all_items`, `get_orphan_items`, `get_trash_items`, `get_items_in_collection`, `get_all_collections`, `get_item_children`, and creator/author resolution) was built and tested exclusively against a hand-typed mock schema that didn't match a real `zotero.sqlite` — verified against an actual Zotero Desktop database (extracted from a local flatpak install) that essentially all offline reads crashed (`no such column: i.parentItemID`, `no such table: collectionData`) or silently mis-resolved creators (`creatorData` table doesn't exist; `creators.firstName`/`lastName` live directly on the row). Fixed the SQL to match: attachment/note parent linkage now resolves via `itemAttachments`/`itemNotes` (real Zotero has no `items.parentItemID`), collection trees resolve `parentCollectionID` (an integer FK) to the parent's key string via a self-join (no `collectionData`/`parentCollection` column), and creator lookups read `firstName`/`lastName` straight off `creators`. Rebuilt both test fixtures (`tests/unit/test_sqlite_repo.py`, `tests/unit/infra/test_sqlite_repo_extended.py`) to match the real schema exactly instead of the previous self-consistent-but-wrong shape, and verified end-to-end against a disposable copy of a real ~15k-item `zotero.sqlite` (never the live file).
- **`collection purge` unreachable (Issue #146):** Registers the `purge` subparser that `_handle_purge` was missing (same dead-dispatch-branch bug class as #161) — `collection purge --name <NAME> --files --notes --tags` now actually works. Also corrected `docs/commands/collection.md`'s stale positional-argument example to the `--name` flag convention every other `collection` verb uses, and added `docs/help_specs/collection_purge.md` per the DOC-SPEC template.

### 🛡️ Quality & Infrastructure
- **SonarQube `python:S5958` cleanup — specific exception type in a VerifyService test (Issue #197):** `test_verify_service_calculate_checksum_error` mocked `zipfile.ZipFile.open` to raise a bare `Exception` and asserted with `pytest.raises(Exception)` — a catch-all that would silently pass even if the wrong kind of failure occurred. `VerifyService._calculate_checksum` doesn't wrap or narrow whatever `zf.open()` raises, so the mock now raises `zipfile.BadZipFile` (what real `zipfile` actually raises for a corrupt/unreadable entry) and the assertion narrows to that same type.
- **SonarQube `python:S8519` cleanup — `next(iter(...))` instead of `list(...)[0]` (Issue #196):** `collection_service.py`'s ambiguous-source resolution and `zotero_api.py`'s `_parse_write_response` each materialized a full `list`/`.keys()` just to take the first element, in both cases already guarded to be non-empty by the surrounding code. Switched to `next(iter(...))`, which gets the same element without the intermediate full-list allocation. No behavior change.
- **SonarQube `python:S8572` cleanup — `logging.exception()` in 6 except blocks (Issue #195):** `resolvers/bdtd.py`, `resolvers/generic_scraper.py`, `snowball_graph.py`, `snowball_ingestion.py`, `snowball_worker.py`, and `infra/bdtd_api.py` each caught an exception and logged it via `logger.error(f"...: {e}")`, discarding the traceback. Switched to `logger.exception(...)`, which captures it automatically — no behavior change, purely a logging-fidelity improvement. Filed as part of a project-wide SonarQube audit of its then-9 open findings (#195/#196/#197).
- **Documentation-consistency protocol formalized (Issue #147):** New `docs/DOC_CONSISTENCY_PROTOCOL.md` — a repeatable 4-step process (ground-truth tree from source → per-leaf structural/reachability/prose checks → record findings → fix and re-verify) for the class of doc drift `pytest tests/docs`'s structural checks can't catch on their own (a documented example that's textually correct but unreachable, or prose describing old behavior). Referenced from `docs/PROCESS.md`'s Phase D and `CLAUDE.md`. See the Bug Fixes entry above for what the protocol's first real pass (once the automated check was actually working) found.
- **`JobQueueService`'s execution model settled; jobs scoped by library (Issue #150):** Documented in `docs/ARCHITECTURE.md` — `zotero-cli` does not grow a persistent daemon (`system jobs run --count N`/`--watch` remain the only ways to drain the queue); an external consumer like Corbenic-SLR's backend owns its own scheduling and observes status via the new `/jobs` API routes above. Separately, `Job`/`jobs.sqlite` had zero per-library scoping — two SLR projects sharing (or both omitting) `--config` would have silently pooled their jobs into one queue with no way to tell them apart. `JobQueueService` now takes a `library_id` (resolved from `config.library_id`/`user_id`, falling back to `"default"`), tags every job it enqueues, and filters every read by it; jobs enqueued before this migration (`library_id IS NULL`) are treated as legacy/unscoped and stay visible everywhere rather than becoming silently orphaned. `SqliteJobRepository` also now explicitly sets `PRAGMA journal_mode=WAL` — deliberate, not incidental, so a status-polling reader doesn't block behind an in-flight worker once this queue is driven by more than one local CLI invocation at a time.
- **`SnapshotService` naming collision resolved; deprecated `CollectionAuditor` shim deleted (Issue #148):** `core/services/snapshot_service.py` and `core/services/slr/snapshot.py` each defined an unrelated class both named `SnapshotService` — one writes JSON collection freezes (`slr report snapshot`), the other diffs two of them (`slr report shift`) — importing "the" `SnapshotService` depended silently on which module you happened to import from. Renamed to `SnapshotWriter` and `SnapshotDiffService` respectively. Separately, `slr report shift` was actually running through `CollectionAuditor`, a class explicitly docstringed `DEPRECATED: ... Maintained for backward compatibility during Phase B` that thinly wrapped `IntegrityService`/`SnapshotDiffService`/`CSVInboundService` — despite the deprecation notice it was the only live code path to the diff logic, not dead code. Deleted `CollectionAuditor` entirely (finishing "Phase B"); `report_cmd.py` now calls `GatewayFactory.get_snapshot_diff_service()`/`get_snapshot_writer_service()` directly instead of instantiating services inline, and the 4 test files that imported the wrapper now exercise `IntegrityService`, `CSVInboundService`, and `SnapshotDiffService` directly. `docs/ARCHITECTURE.md` now states explicitly that the lightweight JSON freeze format and `system backup`'s full ZAF archive format are intentionally separate mechanisms, not meant to converge.
- **`ZoteroGateway.get_trash_items` declared in the contract (Issue #140):** `item_cmd.py::_handle_list` called `gateway.get_trash_items()` on a gateway typed `Any` (a workaround from the #132 mypy-strictness pass, since the real `ZoteroGateway` ABC didn't declare the method the concrete `ZoteroAPIClient` already implemented). Added `get_trash_items` to the `ZoteroGateway` ABC, implemented it on the offline `SqliteZoteroGateway` too (previously missing entirely - `item list --trash --offline` would have crashed with `AttributeError`), and retyped `_handle_list`'s `gateway` parameter back to the honest `ZoteroGateway` type.

### 🔥 Removed
- **Text-to-speech feature removed (Issue #149):** Deleted `item speech`, `core/services/speech_service.py`, `core/utils/speech_filter.py`, the `SpeechProvider` interface, `GatewayFactory.get_speech_service`, and the `tts_lang`/`tts_voice` config fields. Reading a paper aloud isn't part of Zotero library management or SLR tooling — this was flagged as a confirmed removal candidate in an external architecture review and never actioned. The `kokoro`/`soundfile` TTS engine was always a lazy runtime import, never a declared dependency, so no `pyproject.toml`/`uv.lock` change was needed.

## [2.8.3] - 2026-07-26

Resolves both Known Issues disclosed in v2.8.2's release notes.

### ⚠️ Breaking Changes
- **Minimum Python version raised to 3.11 (Issue #166):** Fixes 2 transitive `onnxruntime` path-traversal advisories (PVE-2026-88357/88358, pulled in via `markitdown` -> `magika`) disclosed as a Known Issue in v2.8.2. `onnxruntime` >= 1.24.2 (the first fixed release) ships no Python 3.10 wheels at all, so remediating this required raising the floor rather than a plain version bump. `requires-python`, `.python-version`, both CI workflows, the Docker/dev-container base images, and `sonar-project.properties` are all updated to 3.11; `onnxruntime` is now pinned directly (`>=1.24.2`, resolved to 1.28.0) instead of floating on whatever `magika` happens to pull in. `uv run safety check` now reports zero vulnerabilities.

### 🐛 Bug Fixes
- **`item delete` unreachable (Issue #161):** Registers the `delete` subparser that `_handle_delete` was missing (same bug class as #146) — `item delete --key <KEY>` now actually works, matching the `--key` convention every other `item` verb uses. Also corrected `docs/commands/item.md`'s description, which wrongly called this a "move to trash": the Web API only exposes a hard, permanent `DELETE`, no soft-delete path exists.

## [2.8.2] - 2026-07-25

### ✨ Features & Improvements
- **Duplicate Detection Parity + Improvements (Issue #152):** `report duplicates` now matches by ISBN in addition to DOI/ArXiv/title, and can scan the whole library instead of specified collections (`--collections` is now optional). Items that don't exactly match anything else are additionally compared via a fuzzy fallback tier (title similarity + publication year within 1 year + at least one shared author last-name/first-initial), the same corroborating-signal approach Zotero Desktop uses — including a distinct `preprint-published-pair` label for a preprint matched against its later published version, a common SLR case Desktop's own algorithm doesn't call out explicitly.
- **`item merge` (Issue #155):** New generic, SLR-independent primitive for merging duplicate items — pick a master and one or more duplicates (found via `report duplicates`), and the command unions their tags/collections, moves notes/attachments onto the master, then permanently deletes the duplicates. Conflicting scalar fields (title, date, DOI, ISBN, URL, abstract) require an explicit per-field choice, no silent "first wins". Preview-only by default; `--execute` (plus confirmation, or `--force`) is required to actually write. This is necessarily a one-way, permanent operation — the Zotero Web API only exposes a hard delete, unlike Zotero Desktop's internal, reversible merge mechanism.
- **Bulk merge plans: `report duplicates --export-plan` + `item merge --from-plan` (Issue #156):** `report duplicates` can now export every found group as an editable plan file (`.csv` opens in a spreadsheet with blank role/reason columns; `.json` additionally embeds each occurrence's full SDB screening history for a richer review UI). Fill in which occurrence is the `MASTER`, which are `MERGE`/`KEEP`, and why, then run `item merge --from-plan <file> --execute` to commit every fully-resolved group in one pass. Completeness is all-or-nothing — a single group missing a decision blocks the *entire* plan, not just that group. The same `MergePlan`/`MergeDecision` dataclasses are meant to be built and consumed directly as Python objects (no file round-trip) by a future SLR-aware caller like Corbenic-SLR.
- **`slr dedupe`: SLR-specific duplicate reconciliation (Issue #157):** New command that reuses `report duplicates`'s detection scoped to the SLR source tree (every `raw_*` collection and its phase subfolders, or a given `--sources` set), and classifies each duplicate group by whether existing SDB screening decisions agree (`MATCHING`/`CONFLICTING`/`UNSCREENED`) — relocating that classification out of `report_cmd.py` into `SDBService.classify_decision_agreement`, now shared by both commands. `MATCHING`/`UNSCREENED` groups get an auto-filled merge decision and can be consolidated with `--execute`; `CONFLICTING` groups (independently-screened copies whose decisions genuinely disagree) are always left untouched — export the plan and resolve them via `item merge --from-plan`. Physical consolidation is delegated entirely to `MergeService`; a richer SDB reconciliation note (folded occurrences' own prior decisions and source collections, via an extended `SLROrchestrator.record_duplicate_resolution`) is written per merge, preserving audit history rather than collapsing it into a flat "merged" note. `slr report prisma --dedupe-source` can now also feed a read-only duplicate count into the PRISMA Identification-stage numbers.

### 🛡️ Quality & Infrastructure
- **Distribution path for library consumers (Issue #154):** Documented the decision in `docs/ARCHITECTURE.md` — `zotero-cli` is not published to PyPI and won't be; a consumer like Corbenic-SLR that needs the `core/` services directly should depend on it via a git dependency pinned to a release tag (`pip install git+https://github.com/fchicout/zotero-cli@vX.Y.Z`, or `[tool.uv.sources]`), which needs zero new release infrastructure since every release already gets a git tag. Also fixed a pre-existing unclosed mermaid code fence in that same doc (the "Data Contracts" section, including this new one, was rendering as part of an unclosed code block).
- **`DuplicateFinder` as a Clean Library API (Issue #153):** `DuplicateFinder.find_duplicates`/`compare_collections` now return typed `DuplicateGroup`/`DuplicateOccurrence` dataclasses instead of ad hoc dicts, and no longer `print()` internally — non-fatal issues (e.g. a named collection that doesn't exist) are collected in `self.warnings` for the caller to surface instead. `MergeService`, the merge-plan dataclasses (#155/#156), and `SLRDedupeService` (#157) were all built to the same standard — typed dataclass returns, no stdout side effects, narrow constructor dependencies — completing the four services this issue covers.
- **README & Help-Text Accuracy Sweep:** Refreshed `README.md` to cover features that existed but weren't documented (BDTD import, `system check`, `system demo-sandbox`, Docker/devcontainer packaging, citation snowballing, RAG); fixed several dead command references left over from prior refactors (`slr validate` → `report audit`, `slr graph`/`slr shift`/`report status`/`report prisma` → their real `slr report <verb>` forms). Fixed two real bugs found in the process: `item list --help`'s description/example referenced SDB filtering flags (`--included`, `--criteria`, `--persona`) that were removed from that command in an earlier refactor (that filtering now lives in `slr list`), and `tag purge`'s runtime deprecation warning pointed to `collection purge --tags`, a command that was never implemented. Also fixed `scripts/generate_badges.py` silently dropping the CI status badges on every regeneration.

### ⚠️ Known Issues
- **`item delete` unreachable (Issue #161):** `_handle_delete` is fully implemented and documented in `docs/commands/item.md`, but no `delete` subparser is registered in `item_cmd.py`'s `register_args()`, so the command cannot actually be invoked from the CLI today. Not fixed in this release; filed and tracked separately.
- **Transitive `onnxruntime` advisories (pre-existing, not a regression):** `safety check` reports 2 path-traversal advisories (PVE-2026-88357/88358) in `onnxruntime` 1.20.1, pulled in transitively via `sentence-transformers`. Not a direct dependency and not bumped in this release; tracked for a future dependency-upgrade pass.

## [2.8.1] - 2026-07-19

### ✨ Features & Improvements
- **Deeper Duplicate Analysis (Issue #107):** `report duplicates` now reports which collection each duplicate occurrence came from and whether their SDB screening decisions agree (`MATCHING`/`CONFLICTING`/`UNSCREENED`), plus a `--csv` export flag for audit records.
- **Diagnostic Health Checks (Issue #129):** New `system check` command probes Zotero, Semantic Scholar, Unpaywall, PubMed/NCBI, and the configured LLM/embedding providers, reporting CONNECTED/FAILED/NOT CONFIGURED for each.
- **Onboarding Demo Sandbox (Issue #130):** New `system demo-sandbox` command provisions a temporary collection with 6 mock papers (one pre-seeded with a mock SDB note) so new users can try screening/reporting/RAG commands without touching their real library; `--clean` removes it afterward.
- **Docker / Dev Container / Installer Scaffolding (Issue #131):** Added a root `Dockerfile` (lightweight runtime image packaging the same PyInstaller binary as the standalone releases), `.devcontainer/` for GitHub Codespaces/VS Code, and `install.sh`/`install.ps1` one-line installer scripts fetching the latest release binary.

### 🛡️ Quality & Infrastructure
- **Strict Type Checking (Issue #132):** `mypy`'s `disallow_untyped_defs` is now `true` for `src/` (annotating the ~1050 pre-existing test-function signatures under `tests/` is a separate follow-up, kept lenient via an override for now); fixed all 231 real gaps this surfaced across 69 files.
- **`GatewayFactory` Decomposition:** Split the 941-line, 58-method `GatewayFactory` "God Object" into 5 focused sub-factories (`RepositoryFactory`, `MetadataClientFactory`, `ResolverFactory`, `AIProviderFactory`, `ServiceFactory`); `GatewayFactory` itself is now a thin, fully backward-compatible facade.
- **No More `sys.exit()` in Infra:** Removed all `sys.exit()` calls from gateway construction; invalid configuration (missing credentials, unparseable group URL, unresolved library) now raises a typed `ConfigurationError`, caught cleanly at the CLI boundary.
- **Interface Segregation:** Narrowed `TagService`, `AuditService`, `ExportService`, `CitationGraphService`, `DuplicateFinder`, `SnapshotService`, and `SyncService` off the full `ZoteroGateway` onto the specific narrow repositories (Item/Collection/Tag) they actually use.
- **AI-Ready SDLC Pivot:** Retired the stale Gemini-persona process-doc layer in favor of `CLAUDE.md` + GitHub Issues as the single source of truth; added mechanically-enforced quality gates (pre-commit hooks for ruff/mypy/bandit/pytest) and migrated tooling from pip to `uv`.
- **Documentation Consistency Sweep:** Removed 23 stale doc files describing commands renamed/removed in earlier refactors (`slr reset`/`migrate` → `slr sdb reset`/`upgrade`, `collection duplicates` → `report duplicates`, `find-pdf` → `item pdf`, and others), corrected the README command-reference table's key-verb listings, and fixed `tests/docs` to catch this class of drift going forward (header-row false positive in the Parameter Matrix parser, and new orphan-doc checks for both `docs/help_specs/` and `docs/commands/`).

## [2.7.0] - 2026-05-07

### ✨ Features & Improvements
- **Formal Project Documentation:** Added comprehensive `REQUIREMENTS.md`, `USE_CASES.md`, and `USER_STORIES.md` to the `docs/` directory, establishing a clear functional and user-centric baseline for the project.

### 🛡️ Quality & Infrastructure (The Council Audit)
- **Root Directory Hygiene:** Performed a major cleanup of the project root, moving misplaced data artifacts (`.csv`, `.json`, `.txt`) to the `data/` directory and removing legacy coverage artifacts.
- **Documentation Consolidation:** Synchronized internal architectural notes with user-facing requirements to ensure cognitive clarity across the codebase.

## [2.6.1] - 2026-04-26

### ✨ Features & Improvements
- **SLR Status Dashboard:** Enhanced `slr status` with a new "Tree Total" column and global aggregate rows, providing a 360-degree view of the systematic review funnel across all sources.
- **Traceable Duplicate Auditing:** Implemented forensic duplicate logging; every resolution during system restore is now permanently recorded in SDB Audit Notes for 100% accountability.
- **Dependency Injection Refactor:** Major architectural cleanup of core services using constructor injection, centralized via the `GatewayFactory` for better testability and isolation.
- **Unified Purge Engine:** Consolidated all destructive operations (tag removal, PDF stripping) into a single, high-fidelity `PurgeService` to ensure consistent "Dry Run" and safety checks.

### 🛡️ Quality & Infrastructure (Valerius Protocol)
- **Green State Certification:** Reached a landmark stability milestone with 100% test pass rate, 0 lint/type errors, and 0 warnings.
- **80% Coverage Gate:** Successfully cleared the global 80% code coverage threshold with new unit tests for high-impact SLR commands.
- **Zero-Leak E2E Sentinel:** Integrated a robust `ResourceTracker` in the E2E suite that guarantees remote Zotero resource cleanup even on test failures or crashes.
- **Python 3.14 Modernization:** Hardened the codebase for Python 3.14 compatibility and implemented targeted suppression of legacy library deprecation noise.

## [2.6.0] - 2026-04-21

### ✨ Features & Improvements
- **RAG Verification Engine (Spec v1.1):** Introduced automated integrity checks for semantic search results. Results can now be verified against mandatory academic identifiers (DOI/arXiv) and screening status.
- **Fidelity Integrity Guards:** Enforced high-fidelity JSON serialization in the RAG pipeline. Snippets are now preserved without truncation in `--json` output, ensuring 100% data reliability for citation verification.
- **Citation Key Traceability:** Enhanced the `ZoteroItem` model to automatically extract and verify Citation Keys from the Zotero 'extra' field.
- **Verification CLI:** Added the `--verify` flag to `rag query`, providing real-time feedback on the "verified" status of retrieved context.

### 🛡️ Quality & Infrastructure
- **Restoration Gate:** Established a new safety protocol to verify the integrity of critical research database backups (`.bak_research`) during the test lifecycle.
- **Valerius Protocol Expansion:** Hardened the RAG test suite with exhaustive unit and fidelity tests.
- **Interface Consolidation:** Refactored `RAGService` to use a unified and more flexible ingestion strategy.

## [2.5.0] - 2026-03-14

### ✨ Features & Improvements
- **RAG Core (Issue #93):** Introduced Systematic Knowledge Retrieval. Allows building a local vector store from PDF full-texts and metadata for LLM context injection.
- **BibTeX Engine (Issue #94, #95):** Added direct collection export to `.bib` format. Includes phase-aware screening notes and criteria in the metadata.
- **Universal Item Transfer (Issue #91, #90):** Implemented high-fidelity cross-library move operations. Supports transferring items between personal and group libraries while preserving metadata and unfiled items.
- **Direct DOI Import (Issue #81):** Added `import doi <DOI>` command for instant bibliographic resolution and PDF discovery.
- **Full-Text Resilience:** Integrated `markitdown` for improved PDF-to-Markdown extraction, powering the RAG pipeline.

## [2.4.1] - 2026-01-29

### ✨ Features & Improvements
- **Safe Reset Engine (Issue #52):** Introduced \`slr reset\` command for phase-aware clearing of screening and extraction progress.
- **Granular Purging:** Enhanced \`PurgeService\` to support filtering by reviewer persona and screening phase, ensuring high-fidelity data management.
- **Tag Auto-Cleanup:** Automatic removal of phase-specific tags during reset operations.

## [2.4.0] - 2026-01-29

### ✨ Features & Improvements
- **SDB-Aware Listing (Issue #56):** Enhanced \`list items\` with support for screening database filters (\`--included\`, \`--excluded\`, \`--criteria\`, \`--persona\`, \`--phase\`).
- **Dynamic UX Rendering:** Active SDB filters trigger a specialized table schema showing Decisions, Criteria, and Persona metadata with color-coded status.
- **Auto-Move on Load (Issue #55):** The \`slr load\` command now supports automatic collection movement using \`--move-to-included\` and \`--move-to-excluded\` flags.
- **Improved CSV Matching:** Enhanced \`AuditService\` to handle case-insensitive CSV headers (\`status\`, \`decision\`) for better compatibility with external exports.

## [2.3.0] - 2026-01-22

### ✨ Features & Improvements
- **Semantic CLI Consolidation (Issue #38, #40):** Unified all systematic review commands under the `slr` namespace for improved ergonomics.
- **SLR Protocol Refinement (Issue #48):** Flattened the `slr` command tree (e.g., `slr load`, `slr validate`).
- **SDB v1.2 & Phase Isolation (Issue #49, #50):** Added support for `full_text` screening phase with evidence capture and phase-isolated notes.
- **Retroactive SDB Injection (Issue #32):** New `slr load` command with fuzzy matching for importing external decisions into the library.
- **Pre-flight Environment Checks (Issue #46):** Implemented "Boot Guard" pattern to enforce environment requirements at startup.

### 🛡️ Quality & Infrastructure
- **MSI Installer Support (Issue #45):** Added official Windows MSI installer infrastructure using WiX v4.
- **Hard Coverage Gate (80%):** Successfully reached and enforced the 80% global test coverage threshold.
- **Recursive Deletion (Issue #37):** Refactored collection deletion to be truly recursive, preventing orphaned items.
- **ArXiv DOI Fallback (Issue #35):** Enhanced DOI extraction logic for ArXiv imports using regex on comments and references.
- **Test Hygiene (Issue #36):** Hardened E2E cleanup fixtures to ensure 100% resource reclamation.

## [2.0.0] - 2026-01-17

### 🚀 Major Architectural Shift (v2.0)
- **Service-Oriented Logic:** Completely decomposed the monolithic legacy `client.py` into specialized services (`ImportService`, `AttachmentService`, `CollectionService`).
- **Repository Pattern:** Solidified the persistence layer with a strict Repository Pattern, decoupling business logic from the Zotero API implementation.
- **Legacy Purge:** Successfully "liquidated" all remnants of the `paper2zotero` project name and associated garbage code.

### ✨ Features & Improvements
- **Automated Quality Dashboard:** Implemented `scripts/generate_badges.py` providing real-time quality visualization (Coverage, Lint, Types) in `README.md`.
- **System Maintenance:** Added `system normalize` to convert external CSV formats (IEEE, Springer) into the CLI's Canonical Research Schema.
- **Advanced Operations:** Implemented `review prune` for enforcing mutual exclusivity between collections and `analyze shift` for tracking collection drift.
- **Robust Backup:** Introduced `.zaf` (LZMA-compressed ZIP) system-wide and collection-scoped backup/restore capabilities.

### 🛡️ Quality & Testing
- **The Iron Gauntlet:** Established a comprehensive 221-test suite split into three deterministic categories:
    - `unit`: Fast, isolated logic tests (80% qualitative coverage).
    - `e2e`: Full-stack "Iron Gauntlet" tests against real Zotero API instances.
    - `docs`: Automated consistency checks between CLI help and Markdown documentation.
- **Zero-Tolerance Quality:** Achieved 100% Green status on `ruff check` and `mypy` strict type checking.
- **Automated Test Runner:** Created `scripts/test_runner.sh` for unified, categorized test execution.

### ⚠️ Breaking Changes
- Monolithic `PaperImporterClient` has been removed. Integration must now use `GatewayFactory` to obtain specific services.
- Version `2.0.0` is now the stable baseline for all future systematic review automation.

## [2.0.0-rc1] - 2026-01-16 (Release Candidate)

## [1.2.0] - 2026-01-15

### Architecture
*   **Command Pattern:** Refactored the entire CLI router into a registry-based Command Pattern. Logic is now modularized in `cli/commands/`.
*   **Strategy Pattern:** Implemented the Strategy Pattern for paper importers, enabling easier extension for new bibliographic formats.
*   **Dependency Injection:** Introduced `GatewayFactory` to centralize infrastructure creation and decouple commands from concrete implementations.
*   **Centralized Configuration:** Moved all configuration and global state management to `core/config.py`.

### Features
*   **Decide Alias:** Added `d` alias for `decide` command to speed up manual screening.
*   **Smart Move:** `manage move` and `decide` now support auto-inference of the source collection. If an item belongs to exactly one other collection, it is moved from there automatically. Fails safely on ambiguity.
*   **Persistent State:** Added `--state <FILE.csv>` to `screen` command. Researchers can now resume sessions and track local screening decisions across restarts.
*   **Extended Inspection:** Added `--full-notes` to `inspect` command to display untruncated note content (useful for auditing inclusion/exclusion rationale).

### Fixes
*   **Decide Command:** Fixed critical bug where `decide` failed to move items due to logic duplication. Now delegates to `CollectionService`.
*   **Snapshot:** Fixed `ZeroDivisionError` in `report snapshot` when processing empty collections.
*   **Inspect:** Resolved bug where `inspect --raw` failed due to missing `raw_data` attribute in `ZoteroItem`.

### Quality
*   **Mock Isolation:** Enhanced test suite to mock default configuration paths, preventing local developer configs from leaking into test environments.
*   **Regressions:** Maintained 100% pass rate across 180 unit/integration tests.

## [v1.1.0] - 2026-01-13 (Retrospective)
*   **Configuration:** Added persistent configuration via `config.toml` (XDG Specification).
*   **Precedence:** Established CLI Flags > Env > Config File hierarchy.

## [v1.0.12] - 2026-01-13

### Quality
*   **Tests:** Fixed additional edge cases in `CollectionService` tests for move operations.

## [v1.0.10] - 2026-01-13

### Quality
*   **Tests:** Fixed unit tests for `CollectionService` to correctly mock the new `get_item` optimization.

## [v1.0.9] - 2026-01-13

### Performance
*   **Move Command:** Optimized `manage move` to use direct Item Key lookup (O(1)) instead of scanning the entire source collection (O(N)). Huge speedup for large libraries.

## [v1.0.8] - 2026-01-13

### Bug Fixes
*   **Collection Movement:** Improved robustness of `screen` command item movement. Now correctly handles Collection Keys vs Names and avoids unnecessary API calls if collections haven't changed.

## [v1.0.7] - 2026-01-13

### Features
*   **Bulk Screening:** New headless screening mode via CSV import.
    *   Command: `zotero-cli screen --file decisions.csv ...`
    *   Supports distributed team workflows.

## [v1.0.6] - 2026-01-13

### Bug Fixes
*   **Inspect Command:** Fixed attribute mapping for `date` and `authors`.
*   **Imports:** Fixed missing `Console` import in `info` command.

## [v1.0.5] - 2026-01-13

### Features
*   **Global Flag:** Added `--user` flag to force the tool to use the Personal Library, bypassing any active `ZOTERO_TARGET_GROUP`.

## [v1.0.4] - 2026-01-13

### Features
*   **Command:** Added `zotero-cli inspect` for viewing detailed item metadata and children.
*   **UX:** `zotero-cli list items` now filters out nested items (attachments/notes) for a cleaner view.
*   **UX:** `zotero-cli list items` supports case-insensitive partial collection names.

## [v1.0.3] - 2026-01-13

### Features
*   **Info Command:** New `zotero-cli info` command to display diagnostic configuration.
*   **Usability:** Improved collection name resolution with case-insensitive and partial match support.

## [v1.0.2] - 2026-01-13

### Quality
*   **Test Coverage:** Increased to 82% (Green) by adding comprehensive failure scenarios for API wrappers.
*   **Verification:** Verified full CLI command tree functionality.

## [v1.0.1] - 2026-01-13

### Architecture
*   **SOLID Refactor:** Decoupled `ZoteroAPIClient` (Repository) from `ZoteroHttpClient` (Transport).
*   **SRP Compliance:** Extracted HTTP logic, headers, and rate limiting to a dedicated transport layer.

## [v1.0.0] - 2026-01-13

### Major Changes
*   **Command Tree Refactor:** Completely redesigned CLI structure for better usability.
    *   `import` (file, arxiv, manual)
    *   `screen` (TUI)
    *   `report` (prisma, snapshot)
    *   `manage` (tags, pdfs, duplicates, clean, move, migrate)
    *   `analyze` (audit, lookup, graph)
    *   `find` (arxiv)
    *   `list` (collections, groups, items)
*   **Personal Library Support:** Added `ZOTERO_USER_ID` support. Tools now work with both Group and User libraries.
*   **Universal Import:** Unified `import file` command auto-detects `.bib`, `.ris`, and `.csv`.

### Features
*   **List Groups:** New `list groups` command to discover User Group IDs.
*   **List Items:** New `list items` command to inspect collections.
*   **PRISMA Viz:** Integrated `mmdc` (Mermaid CLI) for high-quality flowchart generation.

### Fixes
*   **Concurrency:** Resolved `If-Unmodified-Since-Version` locking issues during batch migration.
*   **TUI:** Fixed infinite loop in test mocks.

### Breaking Changes
*   Removed top-level commands: `bibtex`, `ris`, `springer-csv`, `ieee-csv`, `freeze`, `audit`, `duplicates`, `tag`, `attach-pdf`. These are now subcommands.
