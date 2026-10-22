"""python -m ledger {build,check,diff,shares,chart,all} [--refresh] [--accession A]"""
import argparse


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m ledger', description=__doc__)
    ap.add_argument('command', choices=['build', 'check', 'diff', 'shares', 'chart', 'all', 'snapshot', 'restore', 'hydrate', 'evidence'])
    ap.add_argument('--refresh', action='store_true', help='re-download the EDGAR submissions index first')
    ap.add_argument('--accession', help='diff: compare this filing instead of the latest')
    ap.add_argument('--field', default='btc_held')
    ap.add_argument('--period', help='evidence: exact period-end date')
    a = ap.parse_args(argv)
    from . import build, checks, diff, shares
    if a.command in ('snapshot', 'restore', 'hydrate'):
        from . import freeze
        result = getattr(freeze, a.command)()
        print(result if result is not None else a.command + ' complete')
        return 0
    if a.command == 'evidence':
        import json
        from .evidence import cite
        rows = build.read('weekly.csv')
        row = next((r for r in reversed(rows) if not a.period or r['period_end'] == a.period), None)
        if row is None:
            ap.error('period unavailable')
        try:
            print(json.dumps(cite(row, a.field), indent=2))
        except ValueError as e:
            ap.error(str(e))
        return 0
    if a.command in ('build', 'all'):
        build.build(refresh=a.refresh)
    if a.command in ('shares', 'all'):
        _, est, res = shares.run(refresh=a.refresh and a.command == 'shares')
        print(f'sats_per_share.csv {len(est)} rows; cover-date residuals of the basic-share roll-forward:')
        for r in res:
            print(f"  {r['from']} -> {r['to']}: estimated {r['estimated']:,} filed {r['filed']:,} "
                  f"miss {r['miss']:+,} ({r['miss_pct']}%)")
    rc = 0
    if a.command in ('check', 'all', 'diff'):
        res = checks.run()
        if a.command != 'diff':
            print(checks.summary(res))
            breaks = [r for r in res if r['status'] == 'BREAK']
            for r in breaks:
                print(f"BREAK {r['period_end']} {r['check']} stated={r['stated']} recomputed={r['recomputed']} "
                      f"tol={r['tolerance']} {r['accession']}")
            rc = 1 if breaks else 0
        if a.command == 'diff':
            print(diff.diff(a.accession, checks=res))
    if a.command in ('chart', 'all'):
        from . import chart
        print(chart.main())
    return rc
