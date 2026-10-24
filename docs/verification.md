# Verification receipt

Purpose: record actual behavior and its limits for the reviewed public v1 snapshot.

Baseline `3c95b9e`: 37 tests passed. Reviewed implementation: **45 tests pass**, Python 3.14.7, on October 21, 2026 America/Detroit. Pinned CI runtime: Python 3.13.7 on Ubuntu 24.04. No dependencies for CLI/tests/SVG; no separate static typechecker is configured. `compileall` verifies all Python modules compile.

## Clean source copy

A scratch source copy under `~/scratch/strategy-8k-ledger/prepublication/` began without `data/raw/` or generated CSVs. Each of these commands succeeded there, with `SEC_USER_AGENT` unset for restoration/hydration:

```bash
python -m ledger restore
python -m ledger hydrate
python scripts/verify_contract.py
python -m unittest discover -s tests -v
python -m ledger all
python scripts/verify_contract.py
python -m ledger diff
python -m ledger evidence --period 2026-10-18 --field btc_held
python -m compileall -q ledger scripts tests
```

Hydration verified all **184** original public resources. Rebuild read **147** candidate filings, classified **93** weekly updates, and produced **97** weekly and **432** instrument rows. All nine table/manifest hashes and the archive hash matched `data/contract.json` before and after `all`. The latest diff reports **267 BTC** purchased and **848,517 BTC** held for October 12–18. Evidence returns original SHA-256 `758fffb5bae03a2b52568ef75168f7fe710e41b46f1092e96fd72425865c99f3` and numbered source lines. Current `basic_shares` is unavailable, and no current sats/share is generated. The latest bridged value is the July 24, 2026 10-Q cover date (accession 0001050446-26-000044): 219,603.97 sats per basic share, with 843,775 BTC held in both bracketing periods.

Real-source and mutation tests cover all parser families, exhibits, quarter-end subperiods, sales, missing values, unsupported headings/columns/tickers, dropped-table headers, table conflicts and amended/replayed periods. Rebuilds replace outputs rather than append. The new offline empty-cache test forbids network, hydrates twice, and compares every file byte. Retry tests simulate actual-client HTTP 429 success and 503 exhaustion without sleeping. Hash corruption refuses before parsing. Missing evidence is an offline `ValueError`. Each repaired defect has a red-before/green-after regression; see [review.md](review.md).

There are zero unexplained `BREAK` rows. Eleven exact reviewed exceptions remain, and five sale cost-basis checks are `INFO` inferences, not accounting passes. The inherited share-count roll-forward has 92 model rows and residuals as large as 1.50%; it is excluded from the sourced chart/consumer answers. Frozen economic rows and CSV columns did not change in this review.

## Portable chart

The scratch copy generated SVG/HTML using only bundled OFL fonts. Optional PNG export ran with Playwright 1.63.0 using the already installed Chromium; a new browser installation was not exercised. The original and scratch results matched byte-for-byte:

- `figures/sunday-tracker@2x.png`, 2400×2260: SHA-256 `cc1ffcf510ec0a9b562fa5770ff5782c2817e55d892104e074f79d663842d4e9`.
- `figures/sunday-tracker.svg`: SHA-256 `29df9ae0cbcdb14bc6cf87f90ee302b91c652f9130f443a990d153b49c0c5089`.

The figure grew to 1200×1130 on 2026-10-22 for the cover-date table. Two renders gave the same PNG bytes. The 1200×1130 inspector passed: 81 text runs, minimum 18 px, 44 px headline, minimum text contrast 6.92:1, no reported clipping/collisions. The figure brief passed with the disclosed agent-only comprehension-test warning. Desktop and 400 px exports were visually inspected; dense tables at 400 px need zoom (labels render at 6 to 15 px). No human comprehension test is claimed. The original visual identity is preserved. Dataviz was absent from the available skill catalog; no categorical palette was introduced.

Tufte checks: shared linear BTC scale, bars at zero, proportional heights, actual date positions, missing values excluded, one latest-period accent, a table for five same-date ratios and a separate, labeled table for six cover-date ranges. No model denominator or forecast is drawn.

## Remaining operational limits

Source hashes and schema contracts rely on the trusted reviewed Git pin. Section citations do not attest arbitrary caller-provided values. Failed builds can leave old output files; concurrent builds and power-interrupted multi-file output writes are unsupported. Automatic amendment supersession, exhaustive SEC-history discovery, fresh live network recovery, fresh browser installation, audited financial accuracy and security certification are unclaimed.

GitHub default-branch, fresh remote clone and CI evidence are recorded separately in [publication.md](publication.md) after execution.
