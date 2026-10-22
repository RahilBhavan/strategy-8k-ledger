"""Concise human summaries, field/period listings and miss hints for the CLI.

The JSON reports stay the machine interface (`--json`); these functions only read them.
"""
import re
from decimal import Decimal as D

WEEKLY = {
    'btc_acquired': ('BTC', 'bitcoin bought in the period'),
    'btc_sold': ('BTC', 'bitcoin sold in the period'),
    'btc_purchase_usd': ('USD', 'aggregate purchase price (sale price in a sale week)'),
    'btc_avg_purchase_price': ('USD per BTC', 'stated average purchase price in the period'),
    'btc_held': ('BTC', 'total bitcoin held at period end'),
    'btc_cost_basis_usd': ('USD', 'aggregate purchase price of all bitcoin held'),
    'btc_avg_cost_basis': ('USD per BTC', 'average purchase price of all bitcoin held'),
    'atm_net_proceeds_usd': ('USD', 'sum of ATM net proceeds across instruments'),
    'atm_total_net_proceeds_stated': ('USD', "ATM table's own printed total"),
    'buyback_usd': ('USD', 'sum of buyback purchase prices'),
    'pref_buyback_remaining_usd': ('USD', 'preferred repurchase authorization remaining'),
    'mstr_buyback_remaining_usd': ('USD', 'MSTR repurchase authorization remaining'),
    'pref_buyback_authorization_increase_usd': ('USD', 'authorization increase approved in this 8-K'),
    'usd_reserve': ('USD', 'stated USD Reserve balance at period end'),
    'usd_cash': ('USD', 'stated USD Cash balance at period end'),
    'basic_shares': ('shares', 'filed Basic Shares Outstanding (Jan-Feb 2025 only)'),
    'assumed_diluted_shares': ('shares', 'filed Assumed Diluted Shares Outstanding (Jan-Feb 2025 only)'),
    'sats_per_basic_share': ('sats per basic share', 'trace only; btc_held x 1e8 / same-date basic_shares'),
}
INSTRUMENT = {
    'shares': ('shares', 'shares sold (ATM) or repurchased (buyback)'),
    'notional_usd': ('USD', 'preferred only: stated notional of shares sold'),
    'amount_usd': ('USD', 'ATM: net proceeds; buyback: aggregate purchase price'),
    'available_usd': ('USD', 'ATM only: remaining capacity at period end'),
}


def unit(field, instrument=False):
    return (INSTRUMENT if instrument else WEEKLY).get(field, ('', ''))[0]


def fields_text():
    out = ['Weekly fields (python -m ledger evidence|trace --period DATE --field NAME):']
    out += [f'  {k:<40} {u:<20} {m}' for k, (u, m) in WEEKLY.items()]
    out += ['', 'Instrument fields (trace/compare with --ticker MSTR|STRC|STRD|STRF|STRK '
            '--action atm_sale|buyback --field NAME):']
    out += [f'  {k:<40} {u:<20} {m}' for k, (u, m) in INSTRUMENT.items()]
    return '\n'.join(out)


def periods_text(rows):
    out = [f'{len(rows)} reporting periods (pass the end date as --period):',
           f"  {'start':<12}{'end (--period)':<16}{'filed':<12}accession"]
    out += [f"  {r['period_start']:<12}{r['period_end']:<16}{r['filed']:<12}{r['accession']}" for r in rows]
    return '\n'.join(out)


def period_hint(period, rows):
    """Explain a missed --period: the containing period, else the nearest ends."""
    head = f'period unavailable: {period} is not a reporting period end date'
    containing = [r['period_end'] for r in rows if r['period_start'] <= period <= r['period_end']]
    if containing:
        return f'{head}; it falls inside the period ending {containing[0]}: use --period {containing[0]}. ' \
               'List all with: python -m ledger periods'
    ends = sorted({r['period_end'] for r in rows})
    before = [e for e in ends if e < period][-1:]
    after = [e for e in ends if e > period][:1]
    near = ' or '.join(before + after) or 'none'
    return f'{head} and no filed period contains it; nearest period ends: {near}. ' \
           'List all with: python -m ledger periods'


def number(value, u):
    if value in (None, ''):
        return 'missing (not disclosed)'
    v = D(value)
    sign, v = ('-' if v < 0 else ''), abs(v)
    text = f'{v:,.2f}' if v != v.to_integral() else f'{int(v):,}'
    if v != v.to_integral() and D(text.replace(',', '')) != v:
        u = (u + ', rounded for display').lstrip(', ')
    return f'{sign}${text}' if u.startswith('USD') else f'{sign}{text} {u}'.rstrip()


def ranges(numbers):
    spans, start = [], None
    for i, n in enumerate(numbers):
        if start is None:
            start = n
        if i + 1 == len(numbers) or numbers[i + 1] != n + 1:
            spans.append(str(start) if start == n else f'{start}-{n}')
            start = None
    return ', '.join(spans)


def _candidates(value):
    v = D(value)
    found = [f'{int(v):,}'] if v == v.to_integral() else [str(v)]
    for scale, word in ((D(10) ** 9, 'billion'), (D(10) ** 6, 'million')):
        for places in (0, 1, 2):
            s = f'{v / scale:,.{places}f}'
            if D(s.replace(',', '')) * scale == v:
                found += [f'${s} {word}', s]
    return found


def value_line(citation, ticker=None):
    """Best-effort row that prints the value; None when not isolated."""
    lines = citation['lines']
    if ticker:
        row = next((l for l in lines if l['text'].startswith(ticker + ' ') and '|' in l['text']), None)
        if row:
            return row
    for cand in _candidates(citation['value']):
        for l in lines:
            cells = [re.sub(r'^\$\s*|\s*\(\d\)$', '', c) for c in l['text'].split(' | ')]
            if cand in cells or ('$' in cand and cand in l['text']):
                return l
    return None


def citation_text(c, ticker=None, indent='  '):
    out = [f"{indent}source   {c['url']}",
           f"{indent}filing   accession {c['accession']}, filed {c['filed']}; sha256 {c['sha256'][:12]}...",
           f"{indent}locator  normalized lines {ranges([l['line'] for l in c['lines']])}"]
    row = value_line(c, ticker)
    if row:
        out.append(f"{indent}value at line {row['line']}: {row['text'][:110]}")
    return out


FOOTER = 'Full source lines and hashes: rerun with --json.'


def evidence_text(c):
    u = unit(c['field'])
    return '\n'.join([f"{c['field']} = {number(c['value'], u)}",
                      f"  period   {c['period_start']} to {c['as_of']}",
                      *citation_text(c), FOOTER])


def _observation(t, label):
    o, ticker = t['observation'], t['observation'].get('ticker')
    u = unit(t['field'], instrument=bool(ticker))
    who = ' '.join(x for x in (ticker, o.get('action'), o.get('program') and f"({o['program']})") if x)
    out = [f"{label}{t['field']}{' for ' + who if who else ''} = {number(t['value'], u)}",
           f"  period   {o['period_start']} to {o['period_end']}"]
    for c in t['evidence']:
        if len(t['evidence']) > 1:
            out.append(f"  operand  {c['field']} = {number(c['value'], unit(c['field']))}")
        out += citation_text(c, ticker)
    if t['field'] == 'sats_per_basic_share':
        out.append(f"  formula  {t['derivation']}")
    return out


def trace_text(r):
    return '\n'.join(_observation(r, '') + [FOOTER])


def compare_text(r):
    after = r['after']
    u = unit(after['field'], instrument=bool(after['observation'].get('ticker')))
    delta = r['delta_after_minus_before']
    sign = '+' if delta and D(delta) > 0 else ''
    change = 'n/a (a side is missing)' if delta is None else sign + number(delta, u)
    head = (f"{after['field']}: {number(r['before']['value'], u)} -> {number(after['value'], u)} "
            f"(change {change}); {r['status']}, {r['kind'].replace('_', ' ')}")
    return '\n'.join([head] + _observation(r['before'], 'before: ') + _observation(after, 'after:  ')
                     + [f"resolution: {r['resolution']}", FOOTER])
