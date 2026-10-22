# Method: fetching and parsing

Purpose: how the ledger finds, caches and reads Strategy's weekly 8-Ks, and how it refuses layouts it does not know.

## Fetch

`ledger/edgar.py` reads EDGAR's submissions index for CIK 1050446 and keeps every 8-K and 8-K/A filed since 2025-01-01 (147 at 2026-10-19). Each document is cached at `data/raw/<accession>/<document>`. `data/raw/manifest.csv` records the URL, UTC fetch time and SHA-256 of every cached file. A cache hit makes no request; `--refresh` re-downloads only the submissions index.

Requests are throttled to about 6-7 per second and retry on 429/503. Network fetches require an identifying `SEC_USER_AGENT` containing a contact email; no email is embedded in the code. Cached rebuilds require no environment variable. Network access can fail or be blocked and is never replaced with synthetic filings.

When an 8-K body has no weekly update but says it furnishes Exhibit 99.1, the parser reads the exhibit found in the filing's `index.json`. This happened for 2025-05-27, 2025-10-14 and 2026-10-13.

## Parse

`ledger/parse.py` reads one document into week rows and instrument rows. Three layout families:

| Family | Period | What it reads |
|---|---|---|
| `prose` | Jan-Mar 2025 | Fixed sentences: "acquired approximately N bitcoins for approximately $X ... average price ...", "held an aggregate of approximately N bitcoins ...", "sold an aggregate of N Shares ... net proceeds ... remained available". |
| `table` | Mar 2025 onward | A period row ("During Period A to B / As of B"), a header row and data rows. ATM rows are labelled `Common ATM`/`STRK ATM` (2025) or `MSTR Stock`/`STRC Stock` (2026). Units come from the header ("in millions") or the cell ("$1.20 billion"). BTC tables are a single row of period and cumulative columns, or two separate tables (from Oct 2026). |
| `sentence` | no-trade weeks | "did not purchase any bitcoin", "Strategy holds approximately N bitcoin that were acquired at ...". |

**Fail loudly.** The parser raises `UnknownLayout` instead of guessing when:

- a table with a trade header (`BTC Acquired/Purchased/Sold`, `Shares Sold`, `Shares Repurchased`) sits under a heading it does not recognise, unless the table spans more than 31 days (quarterly summaries in earnings 8-Ks, which are logged and skipped);
- a header cell, a row label or an amount without a unit is unknown;
- a prose purchase, holdings or ATM sentence does not match the full pattern (counted against a loose pattern);
- two sources in one document disagree (table vs sentence holdings, two different buyback authorizations for one date);
- a USD balance, ATM row or buyback row has a date that matches no holdings date.

Tests in `tests/test_ledger.py` alter real filings (rename a column, rename a heading, reword a sentence, add an unknown ticker) and check that each raises.

**Date assignment.** In the 2025-01-06 8-K, purchases ran Dec 30-31 while holdings and ATM capacity were stated as of Jan 5. A prose period that ends 1-7 days before the only holdings date in the document is assigned to that holdings date, and the decision is written to `data/filings.csv`.

## Attribution

The fetch client, the heading-based section finder, the HTML-to-blocks flattener, `num` and the USD Reserve balance patterns are adapted from [dat-accretion](https://github.com/RahilBhavan/dat-accretion) (`dat/edgar.py`, `dat/parse_mstr.py`), which parses the same 8-Ks from June 2026. That repository was read, not modified. New here: the 2025 prose and table layouts, remaining ATM capacity per program, cumulative cost basis, buyback authorization, the manifest, the checks module, the share-count roll-forward and the chart.
