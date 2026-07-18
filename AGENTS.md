# Stripe Fee Data — Agent Notes

This repository contains the generated Stripe merchant fee data and the
`crawler/` directory that produces it.

## Key commands

- Run crawler tests: `cd crawler && uv run pytest tests/ -q`
- Run lint: `cd crawler && uv run ruff check src tests`
- Run type check: `cd crawler && uv run pyright src`
- Crawl a single market from fixtures: `cd crawler && uv run stripe-fee-crawler crawl-market US --fixture-pricing tests/fixtures/us-pricing.html --output-format summary`
- Discover markets: `cd crawler && uv run stripe-fee-crawler discover-markets`
- Validate a generated data repository: `cd crawler && uv run stripe-fee-crawler validate PATH`
- Strict validation: `cd crawler && uv run stripe-fee-crawler validate PATH --strict --require-all-complete`

## HTTP cache

The crawler keeps a persistent on-disk HTTP cache under
`${XDG_CACHE_HOME:-$HOME/.cache}/stripe-fee-crawler/http` by default. Cache keys
include the URL, method, market, locale, and a crawler-specific version; known
tracking parameters (`utm_*`, `gclid`, `fbclid`) are stripped from the key.

Caching is enabled by default and disabled only by `--no-cache` or
`STRIPE_FEE_CRAWLER_NO_CACHE=true`. `STRIPE_FEE_CRAWLER_NO_CACHE` and
`STRIPE_FEE_CRAWLER_REFRESH_CACHE` are parsed as strict booleans:
`1`, `true`, `yes`, `on` are true; `0`, `false`, `no`, `off`, and empty/unset are
false; other values raise an error.

The configured snapshot TTL (default 24 hours) controls reuse of public pricing
pages. Fresh cached entries are returned without a network request even when the
origin sent `Cache-Control: no-cache` or `max-age=0`. Expired entries are
revalidated with `If-None-Match`/`If-Modified-Since`; a `304 Not Modified`
refreshes the stored timestamp and reuses the body, while a `200` replaces it.
Responses carrying `Cache-Control: no-store` or `private` are never persisted and
any existing stored copy for the same key is removed.

CLI flags: `--cache-dir`, `--cache-ttl-hours`, `--no-cache`, `--refresh-cache`.
Environment variables: `STRIPE_FEE_CRAWLER_CACHE_DIR`, `STRIPE_FEE_CRAWLER_CACHE_TTL_HOURS`,
`STRIPE_FEE_CRAWLER_NO_CACHE`, `STRIPE_FEE_CRAWLER_REFRESH_CACHE`.

Each HTTP request uses a fresh `httpx.AsyncClient` with an empty cookie jar, so cookies
are isolated per request.

## Output layout

The `crawl` command writes `json/`, `meta/`, `schemas/`, and `change-report.json`
under the `--output` directory.

## Classifier tuning points

- `crawler/src/stripe_fee_crawler/classify.py`:
  - `_PAYMENT_METHOD_TOKENS` for recognized method tokens.
  - `_EEA_COUNTRY_CODES` for domestic-region mapping.
  - `_infer_product_id` and `_variant_id_for` for product/variant assignment.
  - `_infer_card_type` and `_infer_card_network` for debit/credit and network splits.
  - `_infer_product_feature`, `_infer_integration_type`, `_infer_payment_method_variant`,
    `_infer_pricing_tier`, `_infer_contract_length`, and `_infer_customer_country`
    for add-on and LPM-specific dimensions.
  - `_is_marketing_or_statistical` excludes platform/marketing numbers from fee rules.
  - `_is_modifier_entry` and `_group_entries` control how fragments are merged
    into logical rows (caps/minimums attach to a base row; `+` surcharges and
    Tap to Pay are standalone rules).
  - `_merge_subset_groups` absorbs partial duplicate rows (e.g. a base fee repeated
    with and without a cap) so they do not surface as conflicts.

## Common test fixtures

- `crawler/tests/fixtures/us-pricing.html`
- `crawler/tests/fixtures/de-pricing.html`
- `crawler/tests/fixtures/de-lpm.html`
- `crawler/tests/fixtures/jp-pricing.html`

## Regeneration and publication

- Regenerate all markets (strict): `cd crawler && make regenerate-strict`
- `make validate` runs formatting, ruff, pyright, and bandit checks.
- The crawler records its Git revision in `meta/crawler-revision.json`; strict
  validation fails if the `crawler/` submodule points to a different commit.
- Strict validation also fails when:
  - derived rules exist but `core-fees.json` is empty,
  - every derived rule for a supported market is non-calculable,
  - a base fee is classified only as a surcharge/modifier,
  - `coverage_summary.blocking_fee_conflicts` is greater than 0,
  - `coverage_summary.dropped_numeric_entries` is greater than 0,
  - `change-report.json` has `has_regression: true`.
- A stale baseline whose `change-report.json` already has `has_regression: true`
  is overwritten with a clean report during the next crawl.
