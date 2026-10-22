# Correctness and publication review

Purpose: record proven repairs to the existing v1, starting at `3c95b9e`, without changing the frozen economics.

Scope: all `ledger/`, CLI, scripts, tests, frozen source/outputs. Baseline: 37 tests pass on Python 3.14.7; clean tree. Correctness, error handling, security, accessibility, performance, dead code and repository conventions were swept. Chart accessibility was measured/rendered separately. No measured performance defect or proven dead-code removal survived. A focused independent T3 read-only scout corroborated six correctness failures; fixes stayed with the owner.

## Fixed and proven

Each regression was executed red before its repair and green afterward; the full suite ran after each slice.

- `ledger/checks.py`: setting October 12, 2025 holdings to `1` was labeled the known one-BTC exception. Known exceptions now match the exact reviewed stated/recomputed/tolerance tuple. A new discrepancy is `BREAK`.
- `ledger/edgar.py`: cache bytes altered without updating their original manifest could enter the parser. Every cached fetch now verifies SHA-256 before returning bytes.
- `ledger/evidence.py`: January 12/20/26 and February 23 share-count citations omitted two-digit date headers. All five denominators now retain their identifying dates.
- `ledger/parse.py`: renaming `Shares Sold` to `Shares Issued` or `Shares Repurchased` to `Shares Bought` silently discarded whole dated tables. Period-bearing security tables now reach strict validation and refuse the changed layout.
- `ledger/build.py`: replaying a filing or adding an overlapping 8-K/A doubled periods and flows. Both refuse before any output writes. Existing real July 31 amendment is non-weekly, so frozen rows are unchanged.
- `ledger/parse.py`: conflicting same-date holdings tables containing `100` then `200` (or reverse) silently selected the last value. Both orders now refuse.
- `ledger/evidence.py`: missing source bytes could initiate an unrequested network fetch and expose a transport exception. Citation reads are offline and missing bytes raise `ValueError`.

## Reproducibility evidence

The 184-resource original-byte archive enables empty-cache offline hydration. A regression hydrates into an empty disk-backed scratch cache, forbids network, then hydrates again and compares every file byte. The pre-existing 429 retry-success and 503 retry-exhaustion cases remain; build replay compares exact output bytes. Contract checks pin all normalized tables, original manifest and archive. A clean clone executes the documented commands separately from this cache; see [verification.md](verification.md).

## Explicit limits and discarded candidates

- `cite(row, field)` supplies source sections, not value attestation for arbitrary caller dictionaries. An edited value can be echoed; this contract is explicit. Consumers must verify table/manifest hashes from a trusted Git pin. Ask Filings implements that boundary. Changing data and its locally writable manifest together is outside the hash-only trust model.
- No automatic amendment selection, exhaustive historical pagination, transaction-level audit, current sourced denominator or security certification is claimed. Unknown layouts/overlaps require review.
- Builds stop on parser failure before normal output writes, but existing outputs can remain stale. CSV publication is not a transactional multi-file database; concurrent builds/snapshots are unsupported. A power interruption can require restore/hydrate and rebuild.
- No unexplained reconciliation breaks in the unchanged snapshot. Eleven reviewed exceptions and five sale cost-relief inferences remain visible, with the original precision limits.
- Public SEC company contact details in original filings are source material, not private user records. Font OFL notices travel with bundled fonts; no project code license was invented.
