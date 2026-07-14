# Stripe Fee Data Repository

[![GitHub last commit](https://img.shields.io/github/last-commit/smeinecke/stripe-fee-data?label=last%20update)](https://github.com/smeinecke/stripe-fee-data)

This repository publishes structured, schema-validated, and deterministic JSON data derived from Stripe's public pricing pages. It is maintained by the [stripe-fee-crawler](https://github.com/smeinecke/stripe-fee-crawler) project.

## Statistics

<!-- STATS_START -->
| Metric | Value |
|--------|------:|
| Markets | **9** |
| Derivation status | 8 partial, 1 unclassified |
| Core fee rules | **0** |
| Payment methods | 30 (ach_direct_debit, alipay, amazon_pay, bacs_direct_debit, bancontact, billie, bizum, blik, card, eps, ideal, klarna, konbini, link, mb_way, mobilepay, multibanco, pay_by_bank, paypal, pix, przelewy24, revolut_pay, satispay, scalapay, sepa_bank_transfer, sepa_direct_debit, swish, twint, upi, wechat_pay) |
| Regions | 5 (asia_pacific, europe, middle_east_africa, north_america, south_america) |
| Unsupported markets | 0 |
| Transient failures | 0 |
| Last crawled | 2026-07-14 07:52 UTC |
<!-- STATS_END -->

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
