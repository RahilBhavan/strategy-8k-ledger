# Evidence trace and comparison slice

2026-10-22. Baseline: clean `dd52b3f`; frozen 97 weekly observations,
432 instrument rows and 184 source resources. Existing section citations and
latest-filing diff are useful, but instrument selection, explicit period pairs
and independent revision inspection are absent from the CLI.

Implement `trace` and `compare` JSON reports, preserving the v1 data contract.

Done conditions:

1. A weekly or exactly selected instrument number reports source URL, accession,
   economic dates, filing date, original-byte SHA-256 and replayable section lines.
   Edited normalized inputs or manifest bytes refuse before reporting.
2. Explicit period pairs report both citations, Decimal deltas, and missing sides
   without converting blanks to zero. Same-date distinct accessions are labeled
   revision candidates; differing values are conflicts, never superseded values.
3. Optional accession selection independently parses a cached filing, allowing
   revision inspection without publishing overlapping periods to weekly.csv.
   Non-weekly filings and ambiguous instrument selections refuse clearly.
4. Sats/basic-share reports require same-date filed weekly basic shares on both
   sides. Latest-period requests refuse rather than use the modeled denominator.
5. Behavioral tests cover real period/instrument evidence, synthetic amendment
   conflicts, duplicates, retry/restart determinism, corruption and missingness.
   Existing retry, build-overlap and source hydration regressions remain green.
6. A five-minute offline walkthrough runs from restore/hydrate, with measured
   limits and unchanged snapshot hashes; CI exercises the new CLI paths.

Non-goals: new data, live completeness, automatic amendment precedence, cell-level
HTML attribution, model denominators, chart/UI changes or changing pinned outputs.
