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

The crawler keeps a 24-hour on-disk HTTP cache under `.cache/stripe-fee-crawler/http/`.
Cache keys include the URL, method, and a crawler-specific version; known tracking
parameters (`utm_*`, `gclid`, `fbclid`) are stripped from the key. Responses carrying
`Cache-Control: no-store` or `private` are not persisted. Expired or `no-cache`/`max-age=0`
responses are revalidated with `If-None-Match`/`If-Modified-Since` before reuse.

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
  - `_is_modifier_entry` and `_group_entries` control how fragments are merged
    into logical rows (caps/minimums attach to a base row; `+` surcharges and
    Tap to Pay are standalone rules).

## Common test fixtures

- `crawler/tests/fixtures/us-pricing.html`
- `crawler/tests/fixtures/de-pricing.html`
- `crawler/tests/fixtures/de-lpm.html`
- `crawler/tests/fixtures/jp-pricing.html`
