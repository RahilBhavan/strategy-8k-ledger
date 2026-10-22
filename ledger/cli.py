"""python -m ledger {build,check,diff,shares,chart,all} [--refresh] [--accession A]"""
import argparse


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m ledger', description=__doc__)
    ap.add_argument('command', choices=['build', 'check', 'diff', 'shares', 'chart', 'all', 'snapshot', 'restore', 'hydrate', 'evidence', 'trace', 'compare'])
    ap.add_argument('--refresh', action='store_true', help='re-download the EDGAR submissions index first')
    ap.add_argument('--accession', help='diff: target filing; trace/compare: replay cached target filing')
    ap.add_argument('--field', default='btc_held')
    ap.add_argument('--period', help='evidence: exact period-end date')
    ap.add_argument('--against-period', help='compare: before period-end date')
    ap.add_argument('--against-accession', help='compare: independently replay before filing')
    ap.add_argument('--ticker', help='trace/compare: instrument ticker (otherwise weekly field)')
    ap.add_argument('--action', choices=['atm_sale', 'buyback'])
    ap.add_argument('--program', help='exact instrument program label; required if ambiguous')
    a = ap.parse_args(argv)
    if a.command in ('trace', 'compare'):
        import json
        from . import report
        try:
            print(json.dumps(report.run(a), indent=2))
        except (ValueError, OSError) as e:
            ap.error(str(e))
        return 0
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
