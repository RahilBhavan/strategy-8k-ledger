# Data schema

Purpose: the column contract for every CSV in `data/`, for people and agents that read them (the issuance-router scenario comparison and deterministic filings CLI). Rebuild with `python -m ledger all`.

## Conventions

- **Money is in whole US dollars**, not millions. A filing figure of "$1.92 billion" is stored as `1920000000`. Per-BTC prices are dollars per bitcoin.
- **Blank means not stated/inapplicable.** `0` usually means a stated zero or table dash. Purchase-only BTC tables also receive `btc_sold=0` as a parser representation. Do not read blanks as zero; see [evidence.md](evidence.md) for derivations.
- **Precision.** Strategy prints most amounts rounded ("$64.02 billion", "$22.1 million"), and BTC counts are "approximately" whole numbers. `*_precision` columns give the value of one unit in the last printed digit (for example `10000000` for "$64.02 billion"). Treat a stored figure as accurate to about half of that.
- **Dates** are ISO `YYYY-MM-DD`. `period_end` is the "As of" date of the BTC holdings figure. `period_start` is usually the first day of the stated "During Period ... to ..." or "between ... and ..."; inferred assignments are documented in [method.md](method.md).
- **Provenance.** Every row has `accession` (EDGAR accession number), `filed` (EDGAR filing date) and `doc_url` (the exact document the figures came from). `doc_role` is `8-K body` or `EX-99.1`. From 2026-10-13 Strategy sometimes moved the weekly tables into Exhibit 99.1. The bytes behind each `doc_url` are cached under `data/raw/<accession>/` and listed with UTC fetch time and SHA-256 in `data/raw/manifest.csv`.
- **Company definitions.** Average and aggregate purchase prices include fees and expenses as stated in the filing. USD Reserve and USD Cash retain the company disclosure definitions. Assumed Diluted Shares Outstanding is a company-defined KPI, not GAAP diluted weighted-average shares.
- **Join keys.** `(accession, period_end)` identifies one week row. Instrument rows join to week rows on the same pair.

## `data/weekly.csv`

One row per BTC holdings date in a weekly 8-K. Most 8-Ks have one row. When an 8-K splits the week at a quarter end (for example 2026-10-05: Sep 28-30 and Oct 1-4), it has one row per sub-period. `period_end` is unique across the file.

| Column | Meaning |
|---|---|
| `accession`, `form`, `filed`, `doc_url`, `doc_role` | Provenance (see above). |
| `fetched_utc` | When `doc_url` was downloaded into `data/raw/`. |
| `period_start`, `period_end` | Reporting period. `period_end` = holdings "As of" date. |
| `layout` | Parser family that read the row: `prose` (Jan-Mar 2025 sentences), `table` (Mar 2025 onward), `sentence` (no-trade weeks stated in one sentence). |
| `btc_acquired` | BTC bought in the period. `0` when the filing says it did not purchase. |
| `btc_sold` | BTC sold in the period (mid-2026 weeks). Blank in prose-era rows. |
| `btc_purchase_usd` | Aggregate purchase price (or sale price in a sale week) for the period, USD. |
| `btc_purchase_usd_precision` | Last printed unit of `btc_purchase_usd`. |
| `btc_avg_purchase_price` | Stated average price per BTC for the period. |
| `btc_held` | Total BTC held at `period_end`. |
| `btc_cost_basis_usd` | Stated aggregate purchase price of all BTC held (cumulative cost basis), USD. |
| `btc_cost_basis_usd_precision` | Last printed unit of `btc_cost_basis_usd`. |
| `btc_avg_cost_basis` | Stated average purchase price per BTC held. |
| `atm_net_proceeds_usd` | Sum of USD ATM net proceeds across instruments in this row's period (from `instrument_weekly.csv`). `0` when the 8-K says no ATM sales; blank when the 8-K says nothing about the ATM. |
| `atm_total_net_proceeds_stated` | The ATM table's own "Total" figure, when printed. |
| `atm_no_sales_stated` | `true` when the 8-K says it "did not sell any shares under its at-the-market offering program" without a table. |
| `buyback_usd` | Sum of buyback aggregate purchase price in the period, USD. Blank before the repurchase tables began (July 2026). |
| `pref_buyback_remaining_usd` | Authorization remaining under the digital credit (preferred) securities repurchase program. |
| `mstr_buyback_remaining_usd` | Authorization remaining under the MSTR common repurchase program. |
| `pref_buyback_authorization_increase_usd` | Increase approved in this 8-K (Sep 8, 2026: +$1.0B; Oct 19, 2026: +$1.0B). |
| `usd_reserve`, `usd_cash` | Stated USD Reserve and USD Cash balances at `period_end` (from Dec 2025 / mid-2026). |
| `basic_shares`, `assumed_diluted_shares` | Company KPI table counts (Basic Shares Outstanding, Assumed Diluted Shares Outstanding), when the 8-K printed them. Only Jan-Feb 2025. |

## `data/instrument_weekly.csv`

Long format: one row per instrument per period per action, as printed. Zero rows are kept, because they carry `available_usd`.

| Column | Meaning |
|---|---|
| `accession` ... `period_end` | As in `weekly.csv`. |
| `ticker` | `MSTR`, `STRK`, `STRF`, `STRD` or `STRC`. STRE (euro, Luxembourg) never appears in these 8-K tables; the parser would tag it `currency=EUR` if it did. |
| `action` | `atm_sale` (at-the-market sale) or `buyback` (repurchase). |
| `program` | Row label as filed, cleaned: `Common ATM`, `2024 Common ATM`, `2025 Common ATM`, `STRK ATM`, `MSTR Stock`, `Sales Agreement` (Jan 2025 prose), and so on. Two MSTR programs appear in the week ending 2025-05-04. |
| `currency` | `USD`. |
| `shares` | Shares sold (ATM) or repurchased (buyback). |
| `notional_usd` | Preferred only: stated notional (liquidation preference) of shares sold. Blank for MSTR and before June 2025. |
| `amount_usd` | ATM: net proceeds after commissions. Buyback: aggregate purchase price. |
| `available_usd` | ATM only: "Available for Issuance and Sale" remaining under that program at `period_end`. |
| `layout` | `prose` or `table`. |

## `data/checks.csv`

Output of `python -m ledger check`. One row per check per week. `status` is `OK`, `KNOWN_EXCEPTION` (explained in [consistency.md](consistency.md)), `INFO` (a measurement, not a pass/fail) or `BREAK` (unexplained; the command exits 1). Columns: `period_end`, `accession`, `check`, `status`, `stated`, `recomputed`, `diff`, `tolerance`, `note`.

## `data/share_anchors.csv`

Cover-page share counts from each 10-Q and 10-K filed since 2024-10-01: `as_of`, `class_a`, `class_b`, `basic` (= A + B), `form`, `accession`, `filed`, `doc_url`, `definition`.

## `data/sats_per_share.csv`

A **model estimate**, not a filed figure. `basic_shares_est` = latest cover-page `basic` on or before `period_end` + MSTR ATM shares sold in later weeks - MSTR shares repurchased. `sats_per_basic_share` = `btc_held` x 100,000,000 / `basic_shares_est`. Columns also name the anchor (`anchor_as_of`, `anchor_url`) and the share flows added. This is not Strategy's "BTC per share" KPI, which uses assumed diluted shares.

## `data/filings.csv`

Every 8-K and 8-K/A filed since 2025-01-01 and what happened to it: `status` = `weekly` (parsed; `weeks` lists the period ends) or `not_weekly` (no BTC holdings update, for example earnings, note offerings or governance). `note` records parser decisions such as an ignored quarterly summary table.

## `data/sourced_sats.csv`

Five same-date filed weekly basic-share denominators only: `period_end`, `btc_held`, `basic_shares`, `sats_per_basic_share`, `doc_url`, `filed`. Ratio = BTC held × 100,000,000 / basic shares, rounded to 0.01 sats for display. This precision is arithmetic, not source precision. The main chart and Ask Filings use this source rule instead of the cover-page roll-forward model.
