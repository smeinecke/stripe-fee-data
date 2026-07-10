# Stripe Fee Data Repository

This repository publishes structured, schema-validated, and deterministic JSON data derived from Stripe's public pricing pages. It is maintained by the [stripe-fee-crawler](https://github.com/smeinecke/stripe-fee-crawler) project.

## Structure

- `json/` — per-market normalized fee data plus consolidated indexes.
- `meta/` — manifests, unsupported markets, schema version info, and change reports.
- `schemas/` — JSON schemas used to validate every published file.

## Determinism

All output is sorted deterministically and written with stable SHA-256 identifiers. Re-running the crawler against identical source pages produces byte-for-byte identical JSON files.

## Disclaimer

This is an unofficial, community-maintained data set. Always refer to [stripe.com/pricing](https://stripe.com/pricing) for the latest, authoritative fee information. Do not use these files for billing or tax calculations without independent verification.

## License

The data and schemas are published under the same license as the crawler.
