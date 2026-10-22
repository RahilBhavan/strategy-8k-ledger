"""Consistency checks over data/weekly.csv and data/instrument_weekly.csv -> data/checks.csv.

Every check compares a figure Strategy stated with one recomputed from other stated figures. Tolerances come from
the precision the filing printed (a cost basis printed as "$64.02 billion" is +/- $5 million). A failure is
reported, never silently corrected. Known, explained exceptions are listed in KNOWN below and in
docs/consistency.md; anything else is a BREAK and `python -m ledger check` exits 1.
"""
import datetime as dt
from decimal import Decimal as D
from . import build

CHECK_FIELDS = ['period_end', 'accession', 'check', 'status', 'stated', 'recomputed', 'diff', 'tolerance', 'note']

# Holdings that differ by 1 BTC from prior holdings + this week's trades. The filings state BTC counts as whole
# "approximately" figures, so a 1 BTC residual is rounding in the filing, not a missing trade. 'reverts' = the next
# week's figure brings the series back to the rolled path; 'persists' = later weeks roll from the new stated level.
KNOWN = {
    ('roll', '2025-10-12'): 'persists: 640,031 + 220 = 640,251; 8-K states 640,250',
    ('roll', '2025-12-14'): 'persists: 660,624 + 10,645 = 671,269; 8-K states 671,268',
    ('roll', '2026-02-16'): 'reverts on 2026-02-22: 714,644 + 2,486 = 717,130; 8-K states 717,131',
    ('roll', '2026-02-22'): 'reverts the 2026-02-16 residual: 717,131 + 592 = 717,723; 8-K states 717,722',
    ('roll', '2026-06-14'): 'reverts on 2026-06-21: 845,256 + 1,587 = 846,843; 8-K states 846,842',
    ('roll', '2026-06-21'): 'reverts the 2026-06-14 residual: 846,842 + 520 = 847,362; 8-K states 847,363',
    ('roll', '2026-08-02'): 'reverts on 2026-08-09: 843,775 - 1,638 sold = 842,137; 8-K states 842,138',
    ('roll', '2026-08-09'): 'reverts the 2026-08-02 residual: 842,138 - 1,690 sold = 840,448; 8-K states 840,447',
    ('roll', '2026-09-27'): 'persists: 846,000 + 1,665 = 847,665; 8-K states 847,666',
    ('avg_cost_basis', '2025-08-10'): '$73,288 x 628,946 BTC = $46.094B, which prints as $46.09B, but the 8-K prints '
                                      '$46.10B: the stated figures disagree by about $0.6M beyond print precision',
    ('continuity', '2025-09-01'): '8-K filed 2025-09-02 covers Aug 26 - Sep 1; the prior 8-K covered Aug 18-24, so '
                                  'Aug 25 falls in neither stated period. Holdings still roll (no unreported BTC).',
}


def d(v):
    return None if v in (None, '') else D(v)


def _half_ulp(v):
    """Half the last printed digit of a USD figure stored in dollars: 1,160,000,000 was printed as $1.16 billion."""
    for unit in (D(10) ** 7, D(10) ** 5):
        if v % unit == 0:
            return unit / 2
    return D(0)


def run(weeks=None, insts=None):
    weeks = weeks if weeks is not None else build.read('weekly.csv')
    insts = insts if insts is not None else build.read('instrument_weekly.csv')
    out = []

    def add(w, check, stated, recomputed, tol, note=''):
        diff = None if stated is None or recomputed is None else stated - recomputed
        ok = diff is not None and abs(diff) <= tol
        status = 'OK' if ok else 'KNOWN_EXCEPTION' if (check, w['period_end']) in KNOWN else 'BREAK'
        if status == 'KNOWN_EXCEPTION':
            note = KNOWN[(check, w['period_end'])]
        out.append({'period_end': w['period_end'], 'accession': w['accession'], 'check': check, 'status': status,
                    'stated': stated, 'recomputed': recomputed, 'diff': diff, 'tolerance': tol, 'note': note})

    prev = None
    for w in weeks:
        held, acq, sold = d(w['btc_held']), d(w['btc_acquired']) or D(0), d(w['btc_sold']) or D(0)
        basis, bprec, avgb = d(w['btc_cost_basis_usd']), d(w['btc_cost_basis_usd_precision']), d(w['btc_avg_cost_basis'])
        # 1. holdings roll: held(t) = held(t-1) + acquired(t) - sold(t)
        if prev:
            add(w, 'roll', held, d(prev['btc_held']) + acq - sold, D(0))
            # 2. period continuity: this period starts the day after the last one ended
            if w['period_start']:
                gap = (dt.date.fromisoformat(w['period_start']) - dt.date.fromisoformat(prev['period_end'])).days
                add(w, 'continuity', D(gap), D(1), D(0), 'days from previous period end to this period start')
        # 3. stated average cost basis vs aggregate cost basis / holdings (company-defined, fees included)
        if basis is not None and avgb is not None and held:
            tol = (bprec / 2) / held + D(1) if bprec else D(1)
            add(w, 'avg_cost_basis', avgb, (basis / held).quantize(D('0.1')), tol.quantize(D('0.1')),
                'stated avg cost vs aggregate purchase price / BTC held; tolerance = half the last printed digit of '
                'the aggregate / BTC held, plus $1 for the rounded average')
        # 4. period average purchase price vs aggregate / BTC acquired
        usd, uprec, avg = d(w['btc_purchase_usd']), d(w['btc_purchase_usd_precision']), d(w['btc_avg_purchase_price'])
        n = acq or sold
        if usd and avg and n:
            # the aggregate is printed to 0.1M or 0.01B, and the BTC count is itself an 'approximately' whole number
            tol = ((uprec / 2) / n if uprec else D(0)) + avg * D('0.5') / n + D(1)
            add(w, 'avg_purchase_price', avg, (usd / n).quantize(D('0.1')), tol.quantize(D('0.1')),
                'tolerance = half the last printed digit of the aggregate / BTC, + rounding of the BTC count, + $1')
        # 5. cost basis roll: basis(t) = basis(t-1) + purchases(t) - avg_basis(t-1) x sold(t)
        if prev and basis is not None and d(prev['btc_cost_basis_usd']) is not None:
            pb, pp = d(prev['btc_cost_basis_usd']), d(prev['btc_cost_basis_usd_precision']) or D(0)
            rec = pb + (usd if acq and usd else D(0)) - (sold * d(prev['btc_avg_cost_basis']) if sold else D(0))
            tol = (bprec or D(0)) / 2 + pp / 2 + ((uprec or D(0)) / 2 if acq else D(0))
            if sold:
                # The filings do not state how cost is relieved on a sale. Report what the stated figures imply.
                removed = pb + (usd if acq and usd else D(0)) - basis
                per = (removed / sold).quantize(D(1))
                band = ((bprec or D(0)) / 2 + pp / 2) / sold
                out.append({'period_end': w['period_end'], 'accession': w['accession'], 'check': 'cost_basis_roll',
                            'status': 'INFO', 'stated': basis, 'recomputed': rec, 'diff': basis - rec, 'tolerance': tol,
                            'note': f'sale week: stated basis fell by ${removed / 10**6:,.0f}M for {sold:,} BTC sold = '
                                    f'${per:,} per BTC (+/- ${band:,.0f} from printed precision) vs prior average cost '
                                    f'${d(prev["btc_avg_cost_basis"]):,}; ' + (
                                        'above average cost beyond print precision, so higher-cost lots appear to have '
                                        'been relieved (inference)' if per - band > d(prev['btc_avg_cost_basis']) else
                                        'not distinguishable from average cost at print precision')})
            else:
                add(w, 'cost_basis_roll', basis, rec, tol)
        # 7. preferred buyback authorization: remaining(t) = remaining(t-1) + increase(t) - preferred buybacks(t)
        rem = d(w['pref_buyback_remaining_usd'])
        if prev and rem is not None and d(prev['pref_buyback_remaining_usd']) is not None:
            spent = sum(d(i['amount_usd']) or D(0) for i in insts if i['accession'] == w['accession']
                        and i['period_end'] == w['period_end'] and i['action'] == 'buyback' and i['ticker'] != 'MSTR')
            rec = d(prev['pref_buyback_remaining_usd']) + (d(w['pref_buyback_authorization_increase_usd']) or D(0)) - spent
            tol = max(_half_ulp(rem), _half_ulp(d(prev['pref_buyback_remaining_usd']))) + D('0.05') * 10 ** 6
            add(w, 'pref_buyback_roll', rem, rec, tol, 'remaining authorization vs prior remaining + stated increase - '
                'preferred buybacks this period')
        # 6. ATM per-instrument net proceeds sum vs the table's stated Total
        rows = [i for i in insts if i['accession'] == w['accession'] and i['period_end'] == w['period_end']
                and i['action'] == 'atm_sale' and i['currency'] == 'USD']
        tot = d(w['atm_total_net_proceeds_stated'])
        if tot is not None and rows:
            s = sum(d(i['amount_usd']) or D(0) for i in rows)
            add(w, 'atm_total', tot, s, D('0.05') * 10 ** 6 * len(rows) if tot % 10 ** 7 else D(5) * 10 ** 6,
                'sum of per-instrument net proceeds vs the Total row (each cell rounded)')
        prev = w
    build.write(build.os.path.join(build.DATA, 'checks.csv'), CHECK_FIELDS, out)
    return out


def summary(results):
    from collections import Counter
    c = Counter((r['check'], r['status']) for r in results)
    return '\n'.join(f'{k[0]:<20} {k[1]:<16} {v}' for k, v in sorted(c.items()))
