# Trace and comparison verification

Verified independently on October 22, 2026, Python 3.14.7.

- `python -m ledger restore`, `hydrate`, and `scripts/verify_contract.py` passed:
  all eight table/manifest pins and the public source archive match the reviewed
  v1 contract. No frozen snapshot or consumer pin changed.
- `python -m unittest discover -s tests -v`: **54 tests passed**, including nine
  new report tests. Existing source corruption, missing-source offline refusal,
  retry/exhaustion, duplicate-period refusal before writes, empty-cache hydration
  and restart tests passed. Network retry tests use controlled responses.
- `python -m ledger all` reproduced 97 weekly and 432 instrument rows. A second
  contract check passed after the build. Compilation and `git diff --check` passed.
- Walkthrough commands independently returned MSTR net proceeds `22000000`,
  holdings delta `267`, and same-filing replay delta `0` / `unchanged`.
  The January 12, 2025 sourced ratio returned two operand citations; the current
  ratio request exited 2 with empty stdout. Repeated subprocess reports were
  byte-identical and left input tables/manifest unchanged.

The reports use the reviewed October 21 snapshot, not live data. Revision-conflict
coverage is synthetic because the snapshot's actual 8-K/A is non-weekly. Section
locators do not establish cell-level attribution. No visual artifacts changed.
