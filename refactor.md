# Refactoring & Optimization Plan

Scope: the `crawler/` submodule (`stripe_fee_crawler`, ~10,300 lines src) plus repo-level
`scripts/`. Goal: reduce complexity, remove confirmed-dead code, restructure oversized
modules, and optimize the hot path — **without removing any currently used feature**.

All output data (`json/`, `meta/`, `schemas/`) must stay byte-identical after every phase
(verified via `change-report.json`), and the full test suite (197 tests) must pass
unchanged.

Sibling plan: `paypal-fee-data/refactor.md` — the repos share architecture and several
antipatterns; fixes proven there apply here (and vice versa).

---

## Current state (measured)

| Metric | Value |
|---|---|
| Largest files | `classify.py` 2,972 lines, `validation.py` 1,319 lines |
| radon average | B (6.26) — better average than paypal, but worse hotspots |
| **F-rated** functions | 4: `_classify_group`, `_infer_conditions`, `_infer_product_id` (classify), `_validate_completeness`, `_validate_market_source_integrity`, `_validate_rule_calculator_ready` (validation) |
| E-rated functions | 5 (incl. `_extract_currency_and_amount`, `_merge_rules`, `_detect_changes`) |
| Public API of `classify.py` | `derive_market_fees` (production), `classify_entries` + `_fixed_amount_minor` (tests only) |
| Import graph | Acyclic — `classify` depends only on `models`, `normalize`, `pricing_tokens` |
| Entry point | `cli.py:main` (console script `stripe-fee-crawler`) |

Unlike paypal (35% data), `classify.py` here is only ~13% pure data (~400 lines) — the
plan emphasizes **function decomposition** over data extraction.

---

## Phase 0 — Fix a latent bug found during analysis

- [ ] **Diverged duplicate regression-kind sets.** `models.ChangeReport._compute_has_regression`
      (models.py:797–826) and `regression.check_regression` (regression.py:341–365) both
      hard-code which change kinds count as regressions, and the sets have **drifted**
      (models.py includes `fee_component_disappeared`, `condition_changed`, `cap_changed`,
      `classification_status_regression`, `calculable_to_non_calculable`,
      `duplicate_identity`, `market_coverage_changed`; regression.py omits them).
      Since `ChangeReport`'s model_validator recomputes `has_regression` anyway, delete
      the recomputation in regression.py (340–366) and keep one `REGRESSION_KINDS`
      constant in models.py. Add a test pinning the set.

---

## Phase 1 — Delete confirmed-dead code (no behavior change)

Verified unreferenced across `src/`, `tests/`, `scripts/`:

- [ ] `classify.py`: `_ADDON_PRODUCTS` (139–144); local `import re as _re` (2882) shadowing
      the top-level import.
- [ ] `pricing_tokens.py`: `OPERATOR_MARKERS` (117). Confirm and remove
      `_detect_decimal_separator` (129–166, no callers found).
- [ ] `http.py`: `CachedSource` dataclass (91–98) + the never-read `cached` parameter
      threaded through `_request`/`get`; `HttpClient.head` (424–431, no callers).
- [ ] `output.py`: `OutputPublisher.data_changed` (411–418) and `write_crawl_report`
      (420–422) — **but see Phase 4**: `data_changed` is exactly what
      `crawler._staging_changed` should be calling; wire it up instead of deleting both.
- [ ] `discovery.py`: `_locale_for_country` (153–157, no callers; both branches return the
      same value); inline the trivial `_canonical_market_code` (179–185, ignores its arg).
- [ ] `exceptions.py`: `FeePageStructureError` (107–110, never raised or imported).
- [ ] `models.py` — unused `CrawlConfiguration` fields, never read anywhere in src:
      `fail_on_warning`, `allow_market_drop`, `keep_diagnostics`, `verbose`,
      `transient_policy` (incl. its validator), `market_manifest_path`.
      **Decision needed** for `atomic` and `allow_partial`: plumbed from the CLI but not
      consumed — wire or deprecate-with-warning; keep the flags parseable.
- [ ] `models.Source.detected_currency` (95): `detect_market` computes a currency but no
      caller ever stores it. **Decision needed**: wire it through `extract_page_source`
      (makes the market_detection currency block useful) or drop field + detection block.
- [ ] `normalize.py`: `normalize_country_code`, `normalize_locale`, `normalize_currency`
      are test-only. Preferred fix (keeps the feature): **use them** in the `Market`
      validators (models.py:53–69) that currently re-implement the same normalization
      inline — removes duplication instead of deleting helpers.

Gate: `make all` equivalent (ruff, pytest) + regeneration produces an empty change report.

---

## Phase 2 — Decompose the complexity hotspots

**classify.py**

- [ ] `_classify_group` (1947–2209, 262 lines, F-rated): split into ~5 helpers along its
      existing seams — condition merging, behavior/channel/unit defaulting, status
      decision cascade, legacy-field extraction, rule assembly.
- [ ] `_infer_conditions` (1402–1577, F): much of it is keyword → `FeeCondition(dimension,
      value)` mapping (settlement timing 1477–1484, transaction_type 1565–1572,
      recurring/managed 1556–1561) — drive from a table (~-40 lines).
- [ ] `_infer_product_id` (1195–1290, F): the ~30 sequential `if _text_has(...)` branches
      re-encode the same keyword→product mapping as `_product_from_heading`'s
      `heading_products` list (1106–1155). **One canonical ordered table serving both**
      (~-45 lines, kills the drift risk between the two lists).
- [ ] `_coverage_summary` (2768–2847): replace ~20 repeated
      `model_copy(update={X: X+1})` bumps with a status→field map + loop (~-30 lines).
- [ ] Collapse the 6–8 ten-line keyword→value inferencers (`_infer_card_tier`,
      `_infer_payment_method_variant`, `_infer_pricing_tier`, `_infer_contract_length`,
      `_infer_pricing_plan`, `_amount_component_type`, …) into one `_first_match(text,
      table)` + small tables (~-45 lines).

**validation.py** (1,319 lines, 3 F-rated functions)

- [ ] `_validate_rule_calculator_ready` (565–667): each independent check block becomes its
      own `_validate_rule_*` function — `_validate_core_fees_semantic` already dispatches
      a list of them (1010–1023), so this is a natural extraction.
- [ ] `_validate_completeness` (1163–1303): extract a `_safe_load(path, validator, errors)`
      helper for the six repeated load/parse blocks, then split the three cross-check
      loops.
- [ ] `_label_references_component` (487–532): replace the hand-rolled 4-level decimal
      branching (with two bare `except Exception`) by reusing
      `pricing_tokens._parse_decimal`.
- [ ] Pre-filter calculable rules once instead of repeating
      `if not _is_calculable_status(...): return` in ~12 validators.

**regression.py**

- [ ] `_detect_changes` (121–324, E): split its five independent phases into
      `_diff_market_set`, `_diff_market_counts`, `_diff_rule_values`,
      `_diff_state_transitions`, duplicate-id detection.

---

## Phase 3 — Structural split (feasible, no import cycles)

**`classify.py` → `classify/` package.** External surface is just `derive_market_fees`,
`classify_entries`, `_fixed_amount_minor` — re-export from `__init__.py`, zero churn:

| Module | Content | ~Size |
|---|---|---|
| `tables.py` | All keyword/pattern constants (26–303, 692–722, 871–888) + embedded tables hoisted from `_product_from_heading`/`_infer_unit` | ~400 |
| `evidence.py` | Predicates, false-positive/marketing detection (306–590, 2700–2738) | ~330 |
| `dimensions.py` | The `_infer_*` family (593–1367, 1580–1692) | ~900 |
| `components.py` | Component building (1694–1863) | ~170 |
| `grouping.py` | Enrich/group/`_classify_group` (1866–2331, post-Phase-2 decomposition) | ~470 |
| `dedup.py` | Signature/merge/dedup (2334–2697) | ~360 |
| `__init__.py` | Coverage/status + public API (2740–2972) + re-exports | ~240 |

Shared predicates (`_text_has`, `_has_base_fee`, `_dedup_repeated_phrases`) go to a small
`_util.py`. Move in dependency order, `pytest -q` after each move.

**`validation.py` → `validation/` package** (schemas.py: `validate_*` wrappers +
`generate_*_schema`; semantic_rules.py: `_validate_rule_*`; publication.py:
publication/integrity/completeness/README checks). Keep all current public names
re-exported from `stripe_fee_crawler.validation`.

---

## Phase 4 — Cross-module dedup & centralization

- [ ] **Allowed-value sets in models.py**: `classification_status` literal set written out
      3× (237–253, 417–433, 640–656), `exactness` 2× (377, 664), `derivation_status` 2×
      (530, 695), `calculator_coverage_status` 2× (538, 703) → module-level frozensets.
- [ ] **Currency knowledge**: `pricing_tokens` owns symbols/codes/exponents;
      `market_detection` owns `_CURRENCY_PATTERNS`/`CURRENCY_BY_COUNTRY`; `validation`
      imports `CURRENCY_SYMBOLS` function-locally (467, 479) → one `currencies.py`,
      imports at module top.
- [ ] **`DIRECT_LOCALE_MARKETS`** defined identically in `market_detection.py:12` and
      `discovery.py:145` → one definition.
- [ ] **Market-share phrase detection** duplicated in `components.py:369–397` and
      `validation.py:745–763` (same list + regex) → one shared helper.
- [ ] **Git-revision readers**: `crawler._crawler_revision` (59–90) vs
      `validation._crawler_submodule_revision` (116–131) → one helper.
- [ ] **Staging-change detection**: `crawler._staging_changed`/`_files_equal` (425–463)
      reimplement `OutputPublisher._list_changed_files`/`data_changed` → use the
      publisher, delete the module-level copies. Same for the duplicated crawl-report
      writers (`crawler._write_crawl_report` vs `OutputPublisher.write_crawl_report`).
- [ ] **Payment-method vocabulary**: `output._family_for_method` (627–655) and
      `extract._infer_payment_method` (189–233) keep separate hard-coded method lists →
      centralize (e.g. `payment_methods.py`).
- [ ] **Pricing-page heuristics**: `http._has_pricing_structure` (214–228) vs
      `discovery._is_pricing_page` signals (346–354) — two drifting copies.
- [ ] **cli.py**: shared Click decorator for the ~11 crawl/cache options duplicated across
      `crawl_cmd` and `crawl_market_cmd` (~-40 lines); hoist function-local imports.
- [ ] **crawler.crawl_market** (118–230): extract the near-identical
      fetch-extract-append blocks for the pricing page and the LPM page into one helper.
- [ ] **Duplicate small helpers**: `regression._country_code` ==
      `validation._country_code_from_item`; `_condition_key_data` vs `_condition_key`
      in validation; ~15 open+`json.load` try/except blocks across validation/regression
      → one `_read_json`.
- [ ] **FeeRule legacy flat fields** (`_sync_legacy_fields`, models.py:443–467) mirrored
      back in `output._to_core_fee_components` and read by regression: document
      `fee_components` as the single source of truth; keep the mirror (published schema)
      but generate it in exactly one place.

---

## Phase 5 — Performance optimizations

Hot path: per-line tokenization (`pricing_tokens`) → extraction (`extract`/`components`)
→ classification (`classify`) per market, inside an async crawl loop.

**High impact — fix together (they compound)**

1. **`pricing_tokens._extract_currency_and_amount` (258–263)**: rebuilds 5 regex pattern
   strings from static `CURRENCY_SYMBOLS`/`CURRENCY_CODES` tables on **every phrase**.
   Precompute the compiled patterns at module level.
2. **`pricing_tokens._extract_exactness` (378–383)**: builds ~20 `\b...\b` regexes per
   call and is called 3× inside `tokenize_fee_text` (415, 429, 433) + again in
   `parse_fee_value` (452). One precompiled alternation, computed once per tokenization.
   Same for `_extract_operators` (434 vs 453).
3. **`components.split_section_body_into_entries` (454–458)**: each line is fully
   tokenized **3×** (`_is_feeish_line`, `_is_market_share_statistic`, then `parsed =
   parse_fee_value(line)`). Parse once per line, derive all three from the result.
4. **Async event loop blocked by CPU work**: `crawl_market` calls the synchronous
   `derive_market_fees` (crawler.py:211) and `extract_pricing_entries` (170, 189)
   directly on the loop thread while holding the semaphore — concurrency collapses to
   serial for the CPU portion. `await asyncio.to_thread(...)` for both.

**Medium**

5. `extract._infer_payment_method` (196–230): ~30-item list literal rebuilt per entry →
   module-level constant.
6. `http_cache._read_entry`/`_write_entry` (385, 408): blocking file I/O of full cached
   bodies inside async `fetch` while holding locks → `asyncio.to_thread` (the flock
   acquire already is).
7. `output.py:166–167`: writes each market file then re-reads it from disk to hash —
   serialize once, hash the in-memory string, write the same string.
8. `output.commit`: `_list_changed_files` runs twice per publish (334 and via
   `_output_dir_exists_and_matches` 336→487), and validate+regression re-read the whole
   tree again — compute the changed set once and reuse.

**Low / cleanup**

9. `http_cache` stats: `model_copy(update=...)` on a frozen pydantic model for every
   counter bump (~10 sites) → mutable counter, build `CacheStats` at the end.
10. `logger.debug("... %s", _normalize_url(url))` runs full URL normalization even when
    debug is off (475, 492, 500) → guard or pass raw url.
11. `classify._dedup` (2622): recomputes `_fee_signature(group[0])` (sorts components)
    per comparison → store signature with the group.
12. `classify._text_has` lowercases per call, dozens of times per entry on the same
    text → lowercase once per entry and thread through.

Benchmark before/after: time a full `crawl` from warm HTTP cache; record in the PR.

---

## Execution order & safety net

| Phase | Risk | Gate |
|---|---|---|
| 0 regression-kinds unification | Low (bug fix) | new pinning test + pytest |
| 1 dead code | Low | pytest + empty change report on regen |
| 5.1–5.3, 5.5 tokenizer perf | Low–Med | byte-identical output + benchmark |
| 2 hotspot decomposition | Medium | pytest after each function |
| 3 package splits | Medium | pytest after each module move; re-exports |
| 4 cross-module dedup | Medium | pytest; schema files unchanged |
| 5.4 async offload | Medium | full crawl comparison run |

Non-negotiable invariants:
- `stripe-fee-crawler crawl/crawl-market/discover-markets/validate/inspect/diff` keep
  accepting all current flags.
- `derive_market_fees`, `classify_entries`, `_fixed_amount_minor`, and every currently
  imported `validation.*` name keep resolving from their current module paths.
- Published output stays byte-identical for identical inputs; no published schema field
  (incl. the FeeRule legacy flat fields) is removed.
- The README-metrics coupling (`_validate_readme_metrics` ↔ `scripts/generate_readme.py`
  output format) is documented, not changed.
