# Consistency checks and known exceptions

Purpose: what `python -m ledger check` tests, the tolerances it uses, and why each exception is accepted. Results are in `data/checks.csv`.

## Checks

| Check | Test | Tolerance |
|---|---|---|
| `roll` | `btc_held(t) = btc_held(t-1) + btc_acquired(t) - btc_sold(t)` | 0 BTC |
| `continuity` | `period_start(t)` is the day after `period_end(t-1)` | 0 days |
| `avg_cost_basis` | stated average cost = `btc_cost_basis_usd / btc_held` | half the last printed unit of the aggregate / BTC held, + $1 |
| `avg_purchase_price` | stated period average = `btc_purchase_usd / btc_acquired` (or `/ btc_sold`) | as above, + the rounding of the "approximately" BTC count |
| `cost_basis_roll` | `basis(t) = basis(t-1) + purchases(t)` | half the last printed units of both bases and the purchase |
| `atm_total` | per-instrument net proceeds sum to the table's Total row | $0.05M per row |
| `pref_buyback_roll` | `remaining(t) = remaining(t-1) + increase(t) - preferred buybacks(t)` | half the last printed unit |

## Results at 8-K 0001193125-26-424688 (filed 2026-10-19)

97 week rows: no unexplained breaks. 87 `roll` OK, 9 known exceptions. All 75 period averages, 72 ATM totals and 13 buyback-authorization rolls reconcile.

## Known exceptions

**Holdings roll, 1 BTC.** Strategy prints holdings and purchases as "approximately" whole numbers. Nine weeks are off by exactly 1 BTC. Six of them come in pairs that cancel the next week; three persist, and later weeks roll from the new stated level. None is larger than 1 BTC.

| Week ending | Residual | Pattern |
|---|---|---|
| 2025-10-12 | -1 | persists |
| 2025-12-14 | -1 | persists |
| 2026-02-16 / 2026-02-22 | +1 / -1 | cancels |
| 2026-06-14 / 2026-06-21 | -1 / +1 | cancels |
| 2026-08-02 / 2026-08-09 | +1 / -1 | cancels (sale weeks) |
| 2026-09-27 | +1 | persists |

dat-accretion documented the three 2026 cases from June onward independently (`KNOWN_FILING_GAPS`, `KNOWN_FILING_REBASES` in its `dat/parse_mstr.py`); this ledger finds the same three plus six earlier ones.

**Period gap, 2025-08-25.** The 8-K filed 2025-08-25 covers Aug 18-24. The 8-K filed 2025-09-02 covers Aug 26 - Sep 1. Aug 25 is in neither stated period. Holdings still roll, so no bitcoin is missing.

**Average cost, week ending 2025-08-10.** $73,288 x 628,946 BTC = $46.094B, which would print as $46.09B. The 8-K prints $46.10B. The stated figures disagree by about $0.6M beyond print precision. This is immaterial and left as filed.

## Measurement, not a check: cost removed on BTC sales

The 8-Ks do not say how cost basis is relieved when bitcoin is sold. In four 2026 sale weeks, the stated aggregate cost fell by more than average cost x BTC sold:

| Week ending | BTC sold | Implied cost removed per BTC | Prior average cost |
|---|---|---|---|
| 2026-06-30 | 1,363 | $117,388 (+/- $7,337) | $75,651 |
| 2026-07-05 | 2,225 | $112,360 (+/- $4,494) | $75,578 |
| 2026-08-02 | 1,638 | $109,890 (+/- $6,105) | $75,476 |
| 2026-08-09 | 1,690 | $88,757 (+/- $5,917) | $75,419 |

Inference: higher-cost lots appear to have been relieved first. This is not stated in the filings; check the 10-Q accounting policy note before using it. The 32 BTC sold in the week ending 2026-05-31 is too small to distinguish at print precision.

## Share-count roll-forward residuals

`sats_per_share.csv` rolls each cover-page count forward with MSTR ATM shares sold. At the next cover date the miss was:

| From | To | Miss | Share of filed count |
|---|---|---|---|
| 2025-02-04 | 2025-05-02 | +3,179,793 | 1.16% |
| 2025-05-02 | 2025-07-31 | +225,355 | 0.08% |
| 2025-07-31 | 2025-10-30 | +522,128 | 0.18% |
| 2025-10-30 | 2026-02-13 | +807,406 | 0.24% |
| 2026-02-13 | 2026-04-26 | -456,104 | -0.13% |
| 2026-04-26 | 2026-07-24 | +5,744,899 | 1.50% |

Positive misses are shares the 8-Ks do not report. The Feb-May 2025 miss lines up in time with the conversion of the 2027 convertible notes (redemption notice Jan 24, 2025). The Apr-Jul 2026 miss is not explained by the 8-Ks; it is an open question. The figure restarts at every cover date, so a miss does not accumulate.
