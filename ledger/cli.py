"""python -m ledger {periods,fields,evidence,trace,compare,diff,build,check,shares,chart,all,...}

evidence/trace/compare print a short summary; add --json for the full report."""
import argparse
import sys


def fail(message):
    """Data/selection refusal: one readable line on stderr, exit 2, no partial output."""
    print('error: ' + message, file=sys.stderr)
    raise SystemExit(2)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m ledger', description=__doc__)
    ap.add_argument('command', choices=['periods', 'fields', 'build', 'check', 'diff', 'shares', 'chart', 'all', 'snapshot', 'restore', 'hydrate', 'evidence', 'trace', 'compare'])
    ap.add_argument('--refresh', action='store_true', help='re-download the EDGAR submissions index first')
    ap.add_argument('--accession', help='diff: target filing; trace/compare: replay cached target filing')
    ap.add_argument('--field', default='btc_held')
    ap.add_argument('--period', help='evidence: exact period-end date')
    ap.add_argument('--against-period', help='compare: before period-end date')
    ap.add_argument('--against-accession', help='compare: independently replay before filing')
    ap.add_argument('--ticker', help='trace/compare: instrument ticker (otherwise weekly field)')
    ap.add_argument('--action', choices=['atm_sale', 'buyback'])
    ap.add_argument('--program', help='exact instrument program label; required if ambiguous')
    ap.add_argument('--json', action='store_true', help='evidence/trace/compare: full JSON report')
    a = ap.parse_args(argv)
    import json
    from . import summary
    if a.command in ('trace', 'compare'):
        from . import report
        try:
            result = report.run(a)
        except (ValueError, OSError) as e:
            fail(str(e))
        text = summary.trace_text if a.command == 'trace' else summary.compare_text
        print(json.dumps(result, indent=2) if a.json else text(result))
        return 0
    from . import build, checks, diff, shares
    if a.command == 'fields':
        print(summary.fields_text())
        return 0
    if a.command == 'periods':
        print(summary.periods_text(build.read('weekly.csv')))
        return 0
    if a.command in ('snapshot', 'restore', 'hydrate'):
        from . import freeze
        result = getattr(freeze, a.command)()
        print(result if result is not None else a.command + ' complete')
        return 0
    if a.command == 'evidence':
        from .evidence import cite
        rows = build.read('weekly.csv')
        row = next((r for r in reversed(rows) if not a.period or r['period_end'] == a.period), None)
        if row is None:
            fail(summary.period_hint(a.period, rows))
        try:
            result = cite(row, a.field)
        except ValueError as e:
            hint = ' (unknown name, or not disclosed for this period)' if 'field unavailable' in str(e) else ''
            fail(f'{e}{hint}; list fields with: python -m ledger fields')
        print(json.dumps(result, indent=2) if a.json else summary.evidence_text(result))
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
