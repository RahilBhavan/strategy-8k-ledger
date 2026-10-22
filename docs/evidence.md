# Field evidence contract

Purpose: explain how every output field connects to its source without inventing cell precision.

Each weekly or instrument row carries `doc_url`, `accession`, `form`, `filed`, `period_start` and `period_end`. Document roles distinguish 8-K bodies from Exhibit 99.1. Fetch UTC is retrieval time, not economic as-of time. Manifest hashes identify original bytes. All populated fields inherit that document citation; blank fields mean missing or inapplicable, never zero.

`cite` is offline and raises `ValueError` for missing/cache/hash failures. It verifies source bytes against the local manifest, not arbitrary caller-provided CSV values; consumers must pin and hash-validate normalized tables and the manifest using [the dependency contract](dependency-contract.md).

`ledger.evidence.cite(row, field)` returns that field/value and numbered normalized source lines. A paragraph is one line; each table row is one line with cells joined by ` | `. Source sections include headers, dates, units and footnotes. These are section-level locators, not claims of cell-level attribution or original HTML line numbers. Use `source_lines(url)` to replay the numbering. The numeric field name is an extraction/schema locator; it is not a source label.

- BTC quantities, aggregate cost and averages cite BTC / combined ATM-BTC sections or matching prose.
- Issuance, shares, notional and remaining capacity cite ATM / combined sections; program names keep separate agreements separate.
- Repurchases and authorizations cite repurchase sections/prose; USD fields cite Reserve/Cash sections/prose.
- Basic and assumed-diluted shares cite their KPI table. Cover-page class A and B counts cite the cover sentence. Cover basic is their sum.
- `atm_net_proceeds_usd` and `buyback_usd` are derived sums of USD instrument amounts. Explicit no-sales prose permits a zero; absence of trade rows alone does not. Authorization increase is new minus prior authorization. Printed precision columns are parser-derived last-unit sizes. `btc_sold=0` can be a parser representation of a purchase-only table, not a separately printed sale statement.
- Period start/end can be inferred by the documented assignment rules in `method.md`; they are not necessarily each printed in every table. Layout is parser metadata. `atm_no_sales_stated=false` means no matching no-sales statement, not proof of a sale.

`python -m ledger evidence --period 2026-10-18 --field btc_held --json` emits a replayable example; without `--json` it prints a short summary. Unsupported/missing fields refuse. For instrument evidence, call `cite` with an `instrument_weekly.csv` row; the Ask Filings CLI provides that interface with ticker/date filters.

`data/sourced_sats.csv` is BTC held * 100,000,000 / basic shares only where the weekly filing prints a same-date denominator (5 rows). It inherits the precision of the rounded filed basic count. `data/cover_sats.csv` bridges the ratio past February 2025 with 10-Q/10-K cover-page share counts. Each row pairs one cover count (class A + class B shares outstanding on the stated date) with the filed `btc_held` for the weekly periods ending on or before and after that date. `sats_low` and `sats_high` bound the ratio on the cover date. A cover date is left out unless the next period starts the day after the earlier one ends and states zero BTC sold, so holdings on the cover date lie inside the range (6 rows, May 2, 2025 to July 24, 2026). Holdings and share counts come from different filings and dates. The range shows that gap; it is not a same-date figure. `sats_per_share.csv` is the inherited cover-count roll-forward **model**, with known unreported flows; it is not used by Ask Filings or the primary chart. The roll-forward is a retrospective reconstruction using economic cover dates, not a point-in-time knowledge model; cover counts can have later filing dates. It is never a router input. Neither ratio is Strategy's assumed-diluted BTC Yield KPI.
