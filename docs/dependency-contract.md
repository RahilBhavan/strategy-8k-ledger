# Portable ledger dependency, v1.1.0

Purpose: keep Ask Filings and the issuance router independent of a mutable sibling checkout.

Pin the public Git repository to a reviewed **full commit SHA**, then run `python -m ledger restore` and `python -m ledger hydrate` in that checkout. No installation, sibling directory, account or network is required for the frozen snapshot. `python scripts/verify_contract.py` checks all restored CSV and manifest bytes plus the bundled archive against `data/contract.json`. Obtain that contract from the same trusted Git pin; changing both data and its mutable manifest is not an integrity proof.

Stable v1 interfaces:

- `ledger.build.read(name)` reads a CSV in this checkout's `data/` and returns string dictionaries, preserving blanks. Supported consumer tables: `weekly.csv`, `instrument_weekly.csv`, `share_anchors.csv`, `cover_sats.csv` (added in 1.1.0; no earlier table changed).
- `ledger.evidence.cite(row, field)` and `source_lines(url)` are offline, section-level source locators. Missing source/cache/hash or unavailable fields raise `ValueError`. They do **not** attest that an arbitrary caller-supplied value equals the document. Consumers must verify normalized table bytes against their pinned contract before answering; do not trust an edited CSV just because a source hash matches.
- CSV column names/order and meanings remain as documented in [schema.md](schema.md). `data/contract.json` names schema `1.1.0`, headers, row counts and SHA-256 for every restored table, manifest and archive. Source fetch times are not economic or knowledge dates.
- A week key is `(accession, period_end)`. In the accepted v1 output, `period_end` is unique. Replayed or amended overlapping periods refuse before output writes; choosing a superseding amendment requires source review. The one frozen 8-K/A (July 31) is non-weekly. No automatic amendment-resolution claim is made.
- An instrument key is `(accession, period_end, action, ticker, program)`. Keep programs separate. October 4 and October 18 extraction values and original hashes are unchanged by this review.

A consumer can package a subset of CSV rows and original HTML, provided it retains column contracts, selected table hashes, the original source manifest entries, fetch timestamps, provenance and this snapshot's date. Record the reviewed ledger SHA alongside that subset. Published CI must use its own snapshot or a commit-pinned dependency, never an absolute sibling path.

The retrospective share roll-forward is a model and may use information filed after an economic date. It is unsuitable for point-in-time backtesting. Current sats/share refuses when no same-date sourced denominator exists; `sourced_sats.csv` has only five early-2025 observations. `cover_sats.csv` adds six 10-Q/10-K cover-date ranges through July 24, 2026; it is not a weekly or current figure. The October 28 daily-dividend proposal was pending at the October 21 snapshot.
