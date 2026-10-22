# Publication receipt

Repository: **https://github.com/RahilBhavan/strategy-8k-ledger** — public, default branch `main`, authenticated publishing identity `RahilBhavan`. Publication explicitly authorized by the user. Original history is preserved; no force push or PR was used.

Reviewed consumer/source pin: **`94c70044aaf14eea2ffb53deffd1a1f36bdec52e`**. Subsequent receipt/README changes are documentation only. Ask Filings and the issuance router received this full public SHA and the [v1.0.0 dependency contract](dependency-contract.md) directly. Every frozen CSV and original manifest byte is unchanged from `3c95b9e`, including October 4 and October 18; consumers need no economic snapshot regeneration.

## Executed remote verification

A fresh clone from the public GitHub URL, with no raw cache and `SEC_USER_AGENT` unset, successfully ran:

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

Results: **45 tests pass**, **184** source resources verified, **147** candidate filings / **93** weekly updates / **97** weekly rows / **432** instrument rows. All contract hashes match before and after rebuilding. The latest demo reports **267 BTC** purchased and **848,517 BTC** held. Requesting latest `basic_shares` refuses with exit **2**; no current sats/share is invented. Figure generation was reproduced byte-for-byte in a clean scratch source copy, including PNG export; see [verification.md](verification.md).

GitHub [CI run 39718727460](https://github.com/RahilBhavan/strategy-8k-ledger/actions/runs/39718727460) completed **successfully** for the reviewed source SHA at **2026-10-22 03:47:30 UTC** (October 21 America/Detroit). Its Ubuntu 24.04 / Python 3.13.7 job ran offline restore/hydrate, contract validation, the 45 real-source/mutation/retry tests, CLI demo/evidence and compile checks. Both action revisions are SHA-pinned; job permissions are `contents: read`; no schedules or paid services were added. The remote `main` ref and default branch were checked against the intended pushed commit. Final receipt-tip verification is recorded in the owning thread, keeping this source pin immutable for consumers.

## Review and publication safety

Seven proven defects were repaired with failing-then-passing regressions: broad exception suppression, unchecked cached bytes, omitted denominator dates, silent table drops, duplicate/amended periods, conflicting table overwrite and unrequested citation network fetches. See [review.md](review.md).

Before pushing, tracked source and all reachable history were scanned for credential patterns, private keys, private artifact names, databases/caches and oversized blobs. No secret/private-artifact matches were found. All 184 archive members were verified against public SEC URL, original-byte hash and size entries. The largest published blob is the 3,895,660-byte original-source archive. No private hub data is present. All staged authored source files were under 20,000 bytes (5,000 estimated tokens), and the configured pre-commit hook passed without bypass.

## Limits retained

This is a frozen October 21, 2026 research corpus, with distinct source-as-of, filing and UTC fetch dates. Discovery is recent-index scoped; overlapping amendments require review. Section citations are locators and need caller table/manifest integrity checks from a trusted Git pin. Filed precision is rounded; eleven exact known exceptions and five sale cost-relief inferences remain visible. No current sourced denominator, security certification, market-data calibration, web deployment or trade is claimed. The October 28 daily-dividend proposal remains pending at the snapshot. **No license file yet**; third-party source and font rights are attributed.

The persistent objective was confirmed active through publication and source CI verification. Completion is recorded by the owning thread after the final receipt-tip checks.
