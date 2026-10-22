"""Strict security and BTC table readers."""
from .parse_types import *

ATM_COLS = {'sharessold': 'shares', 'notionalvalue': 'notional', 'netproceeds': 'proceeds',
            'availableforissuanceandsale': 'available'}
REPO_COLS = {'sharesrepurchased': 'shares', 'aggregatepurchaseprice': 'proceeds'}
DESCRIPTION = re.compile(
    r'^(?:Securities Offered:|Size:|Established:|Class A Common Stock$|[\d.]+% Series A Perpetual \w+ Preferred Stock$|'
    r'Variable Rate Series A Perpetual \w+ Preferred Stock$|stock, \$0\.001 par value|'
    r'\$[\d.,]+ (?:billion|million) of .*established \w+ \d{1,2}, \d{4}$)', re.I)


def row_ticker(label):
    label = re.sub(r'(\s*\(\d\))+$', '', label).strip()
    if label in ROW_TICKER:
        return ROW_TICKER[label]
    if m := re.fullmatch(r'(MSTR|STR[A-Z]) (?:ATM|Stock)(?: (?:Class A Common Stock|[\d.]+% Series A Perpetual \w+ '
                         r'Preferred Stock|Variable Rate Series A Perpetual \w+ Preferred Stock))?', label):
        return m.group(1)
    return None


def security_table(rows, cols, what, kind):
    """ATM / repurchase table -> ([(period, ticker, {col: (value, cell)})], stated total or None).

    Header row is the one whose cells (after an optional 'Security' / 'ATM Program Summary' label) all map to `cols`.
    Every other row must be a period row, a ticker row, a description row or the Total row, or this raises."""
    out, header, period, total = [], None, None, None
    after_total = False
    for r in rows:
        r = [norm(c) for c in r]
        p = [period_of(c) for c in r if period_of(c)]
        if p and not any(row_ticker(c) for c in r):
            starts = [s for s, _ in p if s]
            period = (starts[0] if starts else (period or (None, None))[0], p[-1][1])
            continue
        lab = r[0]
        cand = r[1:] if lab in ('Security', 'ATM Program Summary') else r
        keys = [key(re.sub(r'\(in \w+\)', '', h)) for h in cand]
        if keys and all(any(k.startswith(c) for c in cols) for k in keys) and len(keys) >= 2:
            header = [(next(cols[c] for c in cols if k.startswith(c)), header_scale(h)) for k, h in zip(keys, cand)]
            continue
        if lab.startswith('Total'):
            vals = r[1:] if len(r) > 1 else []
            after_total = True
            if vals and vals[-1] not in ('-',):
                total = vals
            continue
        if after_total and all(re.fullmatch(r'[\d,.$ ]+|-', c) for c in r):
            total = r  # 'Total' on its own row, figures on the next
            continue
        t = row_ticker(lab)
        if t:
            if header is None or period is None:
                raise UnknownLayout(f'{what}: ticker row before header/period: {r!r}')
            if len(r) != len(header) + 1:
                raise UnknownLayout(f'{what}: row {r!r} does not fit header {[h for h, _ in header]}')
            vals = {}
            for (col, scale), c in zip(header, r[1:]):
                if col == 'shares':
                    vals[col] = shares_cell(c, what)
                else:
                    if scale is None and kind == 'atm' and col in ('notional', 'proceeds', 'available') \
                            and not re.search(r'million|billion|^-$', c):
                        raise UnknownLayout(f'{what}: {col} cell {c!r} without unit')
                    vals[col] = cell_amount(c, scale, what)[0]
            if t == 'MSTR' and 'notional' in vals and vals['notional'] == 0:
                vals['notional'] = None  # common stock has no notional; the filing prints '-'
            prog = re.sub(r'(\s*\(\d\))+$', '', lab).strip()
            prog = re.match(r'(?:\d{4} )?(?:Common|MSTR|STR[A-Z]) (?:Stock )?(?:ATM|Stock)', prog).group(0)
            out.append((period, t, vals, prog))
            continue
        if DESCRIPTION.match(lab):
            continue
        raise UnknownLayout(f'{what}: unknown row {r!r}')
    if header is None:
        raise UnknownLayout(f'{what}: no recognised header row')
    return out, total


BTC_PERIOD_COLS = {'btcacquired': ('acquired', 1), 'btcpurchased': ('acquired', 1), 'btcsold': ('sold', -1),
                   'btcpurchased/(sold)': ('signed', 0)}
BTC_AGG = ('aggregatepurchaseprice', 'aggregatesaleprice', 'aggregatepurchase/(sale)price')
BTC_AVG = ('averagepurchaseprice', 'averagesaleprice', 'averagepurchase/(sale)price')


def btc_tables(rows, what):
    """BTC table rows -> list of dicts {period, acquired, sold, usd, usd_prec, avg, held, basis, basis_prec, avgbasis}.

    A header row is followed by exactly one data row. Columns after 'Aggregate BTC Holdings' are cumulative."""
    out, period, header = [], None, None
    for r in rows:
        r = [norm(c) for c in r]
        p = [period_of(c) for c in r if period_of(c)]
        if p and not re.search(r'\d', re.sub(rf'{DATE}', '', ' '.join(r)).replace('During Period', '')):
            starts = [s for s, _ in p if s]
            period = (starts[0] if starts else None, p[-1][1])
            continue
        if header is None:
            header = [(key(re.sub(r'\(in \w+\)', '', h)), header_scale(h)) for h in r]
            continue
        if len(r) != len(header):
            raise UnknownLayout(f'{what}: BTC row {r!r} does not fit header {[h for h, _ in header]}')
        if period is None:
            raise UnknownLayout(f'{what}: BTC row without a period row')
        d, cumulative = {'period': period}, False
        for (h, scale), c in zip(header, r):
            if h == 'aggregatebtcholdings':
                d['held'] = num(c)
                cumulative = True
            elif h in BTC_PERIOD_COLS and not cumulative:
                name, sign = BTC_PERIOD_COLS[h]
                v = num(c)
                if name == 'signed':
                    name = 'sold' if v < 0 else 'acquired'
                d[name] = abs(v)
            elif h in BTC_AGG:
                v, prec = cell_amount(c, scale, what)
                d['basis' if cumulative else 'usd'] = abs(v)
                d['basis_prec' if cumulative else 'usd_prec'] = prec
            elif h in BTC_AVG:
                d['avgbasis' if cumulative else 'avg'] = abs(num(c))
            else:
                raise UnknownLayout(f'{what}: unknown BTC column {h!r}')
        out.append(d)
        header = None
    if header is not None:
        raise UnknownLayout(f'{what}: BTC header without a data row')
    return out


# ---------------------------------------------------------------- prose
