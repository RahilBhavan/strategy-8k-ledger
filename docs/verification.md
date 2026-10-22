# Verification receipt

Purpose: record executed behavior and practical limits. Run on 2026-10-21 America/Detroit with Python 3.14.7.

Executed from the repository root:

```bash
python -m ledger restore
python -m ledger hydrate
python -m unittest discover -s tests -v
python -m ledger all
python -m ledger diff
python -m ledger evidence --period 2026-10-18 --field btc_held
python -m ledger snapshot
```

37 tests pass. Real-source tests reparse 147 candidate filings, compare rebuilt output bytes, check the 97 weekly and 432 instrument rows, validate cached SHA-256 and dates, and exercise prose, tables, exhibits, quarter-end subperiods, missing values, duplicated agreements and sales. Mutations of real documents prove unknown headings/columns/tickers and broken prose refuse. Injected missing purchases produce a roll break. Simulated HTTP 429 retry/success and 503 exhaustion test the actual client without network/sleep. Cache corruption is detected; two hydration passes verify the same 184 sources. No live rate-limit outage was induced.

Frozen shards reproduce the local CSV records. Restart means a fresh CLI process: source cache and outputs survive and replay identically; there is no service or database. Rebuilds do not append duplicates. Parser exceptions stop the build; previously generated outputs can remain stale after a failure, so a failed build is not a freshness signal.

`docs/demo.txt` saves the full successful `all` summary. `docs/evidence-example.json` saves the latest holdings evidence. The consistency report has no unexplained BREAK rows; known exceptions and INFO rows are documented, not promoted to exact reconciliation. No general claim of exhaustive SEC history or audited financial truth is made.

## Chart review

Generated `figures/sunday-tracker.svg`, `card.html`, `alt.txt`, `sunday-tracker@2x.png` (2400×1700) and `feed400.png`. Actual embedded Anton/IBM Plex Sans fonts came from the existing Rahil Design assets; font source/license provenance was retained locally in `figures/fonts/`. No project license was added.

The optional `scripts/render_chart.py` was exercised using Python 3.13.15 and Playwright 1.63.0 installed under `~/scratch/strategy-8k-ledger`; the existing Playwright Chromium was used. `present-data/scripts/inspect_render.py` at 1200×850 passed: 41 text runs, minimum 18px, 44px headline, minimum text contrast 6.92:1, no reported collisions/clipping. `check_figure.py figures/brief.json` passed with an agent-only five-second-test warning. Both desktop PNG and 400px export were visually inspected. The dense phone overview needs zoom; no claim of phone-readable source tables is made. No human comprehension test was performed.

Tufte review: purchase/sale bars share one linear BTC scale and a zero baseline, actual dates set x positions, bar height is proportional to quantity (Lie Factor 1 before pixel rounding), missing values are not zero bars, only the latest purchase is accented, and the five per-share ratios use a table. Ratios use filed same-date basic shares, not the inherited share-count model. The dataviz skill was not present in the installed catalog; no categorical palette was introduced.

Generated large artifacts and raw filings remain local and ignored; committed source, manifest shards and CSV shards reproduce them. Fresh network hydration and fallback-font appearance on other hosts remain unverified.
