# Five-minute evidence and comparison walkthrough

Python 3.11+, stdlib only; run from the repository root at a reviewed Git pin.
No accounts, API keys or network are needed. Each command prints a short summary
(value, units, period, filing URL and the normalized line that holds the value);
add `--json` for the full report with every source line. Selection, integrity and
denominator errors go to stderr with exit code 2 and no partial output. A date that
is not a period end names the period that contains it; `python -m ledger periods`
and `python -m ledger fields` list valid inputs.

```bash
python -m ledger restore
python -m ledger hydrate
python scripts/verify_contract.py

# Trace an exact normalized instrument number to original-byte evidence.
python -m ledger trace --period 2026-10-18 --ticker MSTR --action atm_sale --field amount_usd

# Before = --against-period; after = --period. Strings preserve decimal values.
python -m ledger compare --against-period 2026-10-11 --period 2026-10-18 --field btc_held

# Independently parse a cached filing and compare with its published observation.
python -m ledger compare --against-period 2026-10-18 --period 2026-10-18 --accession 0001193125-26-424688 --field btc_held

# A supported same-date filed denominator, with citations for both operands.
python -m ledger trace --period 2025-01-12 --field sats_per_basic_share

# Expected refusal (exit 2): no current same-date denominator.
python -m ledger trace --period 2026-10-18 --field sats_per_basic_share
```

Expected: the instrument value is `22000000` USD; the holdings comparison shows
`848250` before, `848517` after and `267` after-minus-before. Independent replay
is `same_observation`, `unchanged`, delta `0`. Each populated side retains URL,
accession, form, document role, economic window, filed date, original-byte hash,
retrieval UTC and replayable normalized source lines including units. The report
also names its contract hash. Retrieval time is not a disclosure/economic date.

## Selection and revision semantics

`--ticker` selects instrument rows; otherwise the command selects weekly rows.
`--action` and exact `--program` narrow instrument selection. Two Common ATM
programs coexist on May 4, 2025: omitting the program refuses instead of summing
agreements. Example:

```bash
python -m ledger trace --period 2025-05-04 --ticker MSTR --action atm_sale --program '2024 Common ATM' --field available_usd
```

`--accession` independently parses the target document named in the pinned filing
log; `--against-accession` independently parses the before document. Both remain
offline, read-only and constrained to the reviewed snapshot. For a future reviewed
snapshot containing a weekly amendment, choose the same date on both sides and
supply its two accessions. A changed same-date value is a `revision_candidate`
with `status=conflict`; both citations remain, with no automatic supersession.
Even unchanged revision candidates do not establish which filing governs.
`period_windows_match` and `instrument_identity_matches` expose differences in
windows or program labels. Period deltas are arithmetic differences, not growth
rates or proof that unequal reporting windows have comparable flows.

The current corpus has one 8-K/A, July 31, that is non-weekly. Selecting it refuses.
There is **no empirical weekly-amendment result** in this snapshot. Conflict
handling is verified with explicitly synthetic mutations of real observations;
real weekly amendment evidence is the exact unresolved input for empirical replay.
Build still refuses duplicate/overlapping periods before writing output tables.

## Integrity and limits

The CLI verifies weekly, instrument, filing-log and manifest bytes against
`data/contract.json` before selecting rows; every used source is separately
hash-verified offline. The contract must come from a trusted Git pin. A malicious
change to both contract and data is outside this local hash trust model. Lower-level
`select`, `trace` and `compare` functions trust their caller; use `run`/CLI for the
verified boundary. Legacy `evidence` and `cite` semantics remain unchanged.

Blank inputs become JSON `null`, `status=missing`, and no delta. They are never
zero-filled. An unavailable ratio denominator is an error rather than a null
ratio or model substitution. Delta strings are exact Decimal arithmetic on
rounded normalized inputs; ratios retain arithmetic precision, not source
precision. Section locators are not cell-level proof or original HTML lines.
No current/live coverage, financial advice or automatic amendment precedence is
claimed. Rebuild identity and the v1 schema/data/source pins are unchanged.

Verification measured 2026-10-22 on the implementation host: see the receipt in
[improvement verification](improvement-verification.md). Source spot-check:
[October 19 SEC 8-K, Item 8.01 ATM/BTC tables](https://www.sec.gov/Archives/edgar/data/1050446/000119312526424688/mstr-20261019.htm),
reopened 2026-10-22; corroborates $22.0M MSTR net proceeds and 848,517 BTC held.
No new vendor dataset or source bytes were added.
