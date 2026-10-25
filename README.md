# Strategy 8-K ledger: trace weekly treasury fields to SEC filings

Strategy (formerly MicroStrategy) reports its bitcoin buying to the SEC every week; this tool turns those reports into checked tables where every number links back to the filing it came from.

[![CI](https://github.com/RahilBhavan/strategy-8k-ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/RahilBhavan/strategy-8k-ledger/actions/workflows/ci.yml)

![Strategy purchased 267 BTC in the latest period. Sats per basic share comes from five same-date weekly 8-K share counts in early 2025, then six 10-Q/10-K cover share counts through July 24, 2026, each shown as a range.](figures/sunday-tracker@2x.png)

A local Python CLI extracts Strategy's weekly bitcoin, ATM issuance, remaining capacity, repurchases and disclosed USD balances. The frozen corpus contains 97 period rows from 93 weekly updates, through the October 19, 2026 filing. Values retain source URLs and dates; consistency checks expose rounding exceptions instead of silently correcting them.

## What it does

- Reads 147 candidate 8-K/8-K/A filings filed January 6, 2025–October 19, 2026; writes 97 period rows and 432 instrument/program/action rows. See `data/filings.csv`, `weekly.csv` and `instrument_weekly.csv` after restore/build.
- Latest period, October 12–18: 267 BTC purchased, 848,517 BTC held, $22M MSTR ATM net proceeds and $4.83B USD Reserve. See `data/weekly.csv` and [primary filing](https://www.sec.gov/Archives/edgar/data/1050446/000119312526424688/mstr-20261019.htm).
- Checks holdings/cost rolls, dates, stated averages, ATM totals and authorization rolls. No unexplained breaks in the frozen corpus; known exceptions remain visible in `data/checks.csv`.
- Produces a purchase/sale chart and a sats-per-basic-share table. Weekly 8-Ks printed a basic share count only from January 12 to February 23, 2025, so the 8-K rows stop there. Six later rows use the share count on each 10-Q/10-K cover page, paired with the 8-K holdings for the weeks ending before and after the cover date. The latest is July 24, 2026 (Q2 2026 10-Q, accession 0001050446-26-000044): 384,225,751 basic shares, 843,775 BTC, 219,603.97 sats per basic share. See `data/sourced_sats.csv` and `data/cover_sats.csv`.

## How it works

`ledger/edgar.py` caches source bytes with a SHA-256 manifest. Strict prose/table readers reject unknown layouts; `build.py` writes CSVs, `checks.py` reconciles them and `evidence.py` supplies numbered normalized source sections per field. Small `data/frozen/` shards (the output CSVs and manifest, split into 16-row files that stay under the repository's file-size cap) preserve the reviewed outputs. A 3.9 MB archive preserves all 184 original public source resources; `hydrate` unpacks them into the local cache and checks each hash, so evidence works offline. `data/contract.json` is the dependency contract: it pins the table, manifest and archive hashes that downstream tools check.

## Run it

Python 3.11+; tested with Python 3.14.7. No dependencies for the CLI, tests or SVG chart.

```bash
git clone https://github.com/RahilBhavan/strategy-8k-ledger.git
cd strategy-8k-ledger
python -m ledger restore
python -m ledger hydrate
python scripts/verify_contract.py
python -m unittest discover -s tests -v
python -m ledger all
python -m ledger diff
python -m ledger evidence --period 2026-10-18 --field btc_held
```

`restore` rebuilds the CSVs from the frozen shards; `hydrate` unpacks the original filings. The evidence command prints a short answer; add `--json` for every source line and hash:

```text
btc_held = 848,517 BTC
  period   2026-10-12 to 2026-10-18
  source   https://www.sec.gov/Archives/edgar/data/1050446/000119312526424688/mstr-20261019.htm
  filing   accession 0001193125-26-424688, filed 2026-10-19; sha256 758fffb5bae0...
  locator  normalized lines 50-57, 77-78, 82
  value at line 55: 267 | 22.1 | 82,900 | 848,517 | 64.02 | 75,446
```

`python -m ledger periods` lists the 97 valid `--period` dates (period end dates) and `python -m ledger fields` lists field names with units. A date that is not a period end gets an error naming the period that contains it.

`diff` summarizes the latest filing against the prior week (excerpt):

```text
Strategy weekly 8-K 0001193125-26-424688, filed 2026-10-19
  period: 2026-10-12 to 2026-10-18
Bitcoin
  held          848,250 -> 848,517 BTC (+267)
  acquired      267 BTC for $22.1M
  roll check    848,250 + 267 - 0 = 848,517; stated 848,517 OK
  USD Reserve   $4.88B -> $4.83B (-$50.0M)
ATM sales (net proceeds; capacity = remaining "available for issuance and sale")
  MSTR  sold 140,872 shares for $22.0M; capacity $18.81B -> $18.79B (-$22.0M)
Consistency checks for this filing: all OK
```

Observed: **60 tests pass** on Python 3.14.7. The frozen restore, hydrate, tests and demo are offline, including an empty source cache. Python 3.13.7 is pinned in CI. There is no separate typechecker; CI also compiles every Python module.

`build --refresh` opts into live discovery and needs an identifying `SEC_USER_AGENT` containing a contact email. It does not rewrite frozen shards until `snapshot` is explicitly run. SEC failures or changed hashes refuse; no substitute data is generated. For consumer pins and trust boundaries, see the [v1 dependency contract](docs/dependency-contract.md).

Optional PNG export (requires `uv` and an installed Playwright Chromium):

```bash
uv run --with playwright==1.63.0 python scripts/render_chart.py
```

The SVG/HTML embeds the bundled OFL-licensed Anton and IBM Plex Sans fonts. The PNG above is committed; `python -m ledger chart` rebuilds the SVG/HTML. The chart is reviewed at 1200×1130.

`trace` selects weekly or instrument evidence; `compare` reports explicit period
pairs and independently replayed filings, retaining both sides and missing values.
See the [five-minute walkthrough and revision limits](docs/trace-compare.md).

```bash
python -m ledger compare --against-period 2026-10-11 --period 2026-10-18 --field btc_held
python -m ledger trace --period 2026-10-18 --ticker MSTR --action atm_sale --field amount_usd
```

## Repository layout

- `ledger/`: discovery, parser, checks, evidence, share model and chart CLI.
- `data/frozen/`: small CSV shards of outputs and source manifest.
- `data/raw/`: ignored hydrated source cache.
- `data/sources/`: original public SEC bytes with provenance and rights notes.
- `tests/`: actual-source, mutation, integrity and retry tests.
- `figures/`: chart brief, alt text and local exports.
- `scripts/`: optional PNG exporter.
- `docs/`: scope, method, schema and verification receipts.

## Documentation

- [Public design system](DESIGN.md): Rahil Design 3.3.0, shared tokens and visual review rules.

- [Spec](docs/spec.md): accepted v1 and criteria.
- [Method](docs/method.md): fetching and strict parsing.
- [Schema](docs/schema.md): field definitions and units.
- [Evidence](docs/evidence.md): source lines, formulas and missingness.
- [Consistency](docs/consistency.md): tolerances and known exceptions.
- [Sources](docs/sources.md): primary-site review and coverage limits.
- [Verification](docs/verification.md): exact checks and artifact limits.
- [Dependency contract](docs/dependency-contract.md): versioned columns, hashes and consumer pins.
- [Review](docs/review.md): proven fixes and remaining limits.
- [Publication](docs/publication.md): public source pin, fresh-clone and CI evidence.

## Sources

SEC EDGAR CIK 1050446: weekly 8-Ks plus the cover pages of the eight 10-Q/10-K filings since October 2024 (latest: Q2 2026 10-Q, filed August 3, 2026). Review as of October 21, 2026; latest economic date October 18. All 184 cached resources are hashed in the frozen manifest. See [source review](docs/sources.md). The client/block-parser approach adapts Rahil’s dat-accretion work; see attribution in the method. Third-party filings retain their own rights.

## Scope and limits

- Independent local research, not affiliated with Strategy. No scheduler, trades or web deployment.
- Recent submissions index only; no claim of complete historical discovery. Overlapping/amended weekly periods and conflicting tables refuse pending review; new layouts require review.
- Filed rounded values are not audited transaction-level records. Blank means missing/inapplicable. Primary pages were spot-checked, not every filing manually reviewed.
- Sats per share after February 2025 uses quarterly cover share counts, so it updates only when a 10-Q or 10-K is filed. The holdings come from the 8-K weeks either side of the share date, so each row is a range, not a same-date figure. No current weekly ratio is computed.
- The separate share roll-forward (`data/sats_per_share.csv`) is a labeled model that misses some share flows; it is not used in the chart or Ask Filings.
- October 28 daily-dividend proposal remains pending as of October 21; no enactment assumption.

## License

[MIT](LICENSE). The license covers this project's code only. Third-party filings and font assets retain their own terms.

Part of [Rahil Bhavan's projects](https://github.com/RahilBhavan).
