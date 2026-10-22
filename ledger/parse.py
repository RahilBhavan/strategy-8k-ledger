"""Weekly document orchestration; public parser interface."""
from .parse_types import *
from .parse_tables import *
from .parse_prose import *

def parse_document(html_text, what):
    bs = [(k, norm(v) if k == 'p' else v) for k, v in blocks(html_text)]
    secs = sections(bs)
    text = ' '.join(v for k, v in bs if k == 'p')
    weeks, inst, notes = {}, [], []

    def week(end, layout):
        return weeks.setdefault(end, {'layout': layout})

    def table_update(w, **values):
        for field, value in values.items():
            if value is not None and w.get(field) is not None and w[field] != value:
                raise UnknownLayout(f'{what}: conflicting table values for {field}: {w[field]} and {value}')
            if value is not None:
                w[field] = value

    for kind, sec in secs:
        tables = [v for k, v in sec if k == 'table']
        trade_tables = [t for t in tables if any(TRADE_HEADER.match(norm(c)) for r in t for c in r)]
        if kind is None:
            for t in trade_tables:
                p = next((period_of(c) for r in t for c in r if period_of(c)), None)
                if p and p[0] and (dt.date.fromisoformat(p[1]) - dt.date.fromisoformat(p[0])).days > 31:
                    notes.append(f'ignored multi-week summary table {p[0]}..{p[1]} (quarterly update)')
                    continue
                raise UnknownLayout(f'{what}: trade table outside a recognised weekly section: {t[:2]!r}')
            continue
        if kind in ('btc', 'atm+btc'):
            for t in tables:
                cells = [norm(c) for r in t for c in r]
                if not any(re.match(r'BTC ?(?:Acquired|Purchased|Sold)|Aggregate ?BTC ?Holdings', c) for c in cells):
                    continue  # KPI share-count table, footnotes, or an ATM table in a combined section
                for d in btc_tables(t, what):
                    s, e = d['period']
                    w = week(e, 'table')
                    if s:
                        table_update(w, period_start=s)
                    if 'held' in d:
                        table_update(w, btc_held=d['held'], btc_cost_basis_usd=d.get('basis'),
                                 btc_cost_basis_usd_precision=d.get('basis_prec'), btc_avg_cost_basis=d.get('avgbasis'))
                    if 'acquired' in d or 'sold' in d or 'usd' in d:
                        table_update(w, btc_acquired=d.get('acquired', Decimal(0)), btc_sold=d.get('sold', Decimal(0)),
                                 btc_purchase_usd=d.get('usd'), btc_purchase_usd_precision=d.get('usd_prec'),
                                 btc_avg_purchase_price=d.get('avg'))
        if kind in ('atm', 'atm+btc'):
            for t in tables:
                if not (any(re.match(r'Shares Sold', norm(c)) for r in t for c in r)
                        or (any(r and row_ticker(norm(r[0])) for r in t)
                            and any(period_of(c) for r in t for c in r))):
                    continue
                rows, total = security_table(t, ATM_COLS, what, 'atm')
                for (s, e), tick, v, prog in rows:
                    inst.append(Instrument(s, e, tick, 'atm_sale', 'table', shares=v.get('shares'),
                                           notional_usd=v.get('notional'), amount_usd=v.get('proceeds'),
                                           available_usd=v.get('available'),
                                           currency='EUR' if tick == 'STRE' else 'USD', program=prog))
                if total is not None and rows:
                    e = rows[-1][0][1]
                    c = total[-1] if len(total) == 1 else total[-2] if len(total) >= 2 else total[-1]
                    scale = SCALE['million'] if 'millions' in ' '.join(' '.join(r) for r in t) else None
                    try:
                        week(e, 'table')['atm_total_net_proceeds_stated'] = cell_amount(total[0], scale, what)[0]
                    except UnknownLayout:
                        notes.append(f'ATM total cell not parsed: {total!r}')
        if kind == 'repurchase':
            for t in tables:
                if not (any(re.match(r'Shares Repurchased', norm(c)) for r in t for c in r)
                        or (any(r and row_ticker(norm(r[0])) for r in t)
                            and any(period_of(c) for r in t for c in r))):
                    continue
                rows, _ = security_table(t, REPO_COLS, what, 'repurchase')
                for (s, e), tick, v, prog in rows:
                    inst.append(Instrument(s, e, tick, 'buyback', 'table', shares=v.get('shares'),
                                           amount_usd=v.get('proceeds'), currency='EUR' if tick == 'STRE' else 'USD',
                                           program=prog))
            stext = ' '.join(v for k, v in sec if k == 'p')
            if not any(k == 'table' for k, _ in sec) and not re.search(r'did not (?:re)?purchase any shares', stext):
                raise UnknownLayout(f'{what}: repurchase section with no table and no "did not purchase" sentence')

    pw, pinst, orphan = prose(text, what)
    for e, d in pw.items():
        w = weeks.setdefault(e, {'layout': 'prose'})
        for k2, v in d.items():
            if w.get(k2) is not None and v is not None and w[k2] != v:
                raise UnknownLayout(f'{what}: {k2} for {e} differs between table ({w[k2]}) and prose ({v})')
            w.setdefault(k2, v)
            if w[k2] is None:
                w[k2] = v
    have = {(i.ticker, i.period_end) for i in inst}
    inst += [i for i in pinst if (i.ticker, i.period_end) not in have]

    for m in P_HOLDS.finditer(text):
        e = iso(m.group(1))
        w = weeks.setdefault(e, {'layout': 'sentence'})
        held = Decimal(m.group(2).replace(',', ''))
        if w.get('btc_held') not in (None, held):
            raise UnknownLayout(f'{what}: holdings sentence {held} disagrees with table {w["btc_held"]}')
        w['btc_held'] = held
        if m.group(3) and w.get('btc_cost_basis_usd') is None:
            w['btc_cost_basis_usd'] = money(m.group(3), m.group(4))
            w['btc_cost_basis_usd_precision'] = ulp(m.group(3), SCALE[m.group(4)])
        if m.group(5) and w.get('btc_avg_cost_basis') is None:
            w['btc_avg_cost_basis'] = Decimal(m.group(5).replace(',', ''))
    if re.search(r'did not purchase (?:or sell )?any bitcoin', text):
        m = re.search(rf'(?:between|from) ({DATE}) (?:and|to|through) ({DATE})[^.]*?did not purchase (?:or sell )?any bitcoin',
                      text)
        if m and iso(m.group(2)) in weeks:
            w = weeks[iso(m.group(2))]
            w.setdefault('period_start', iso(m.group(1)))
            if w.get('btc_acquired') is None:
                w['btc_acquired'] = Decimal(0)

    if m := re.search(rf'between ({DATE}) and ({DATE}),[^.]*?did not sell any shares under its at-the-market offering '
                      r'programs?(?! for)', text):
        if iso(m.group(2)) in weeks:
            weeks[iso(m.group(2))]['atm_no_sales_stated'] = True
    weekly = {e: w for e, w in weeks.items() if w.get('btc_held') is not None}
    if not weekly:
        if weeks or inst:
            raise UnknownLayout(f'{what}: weekly trade data found but no BTC holdings figure')
        raise NotWeekly('no BTC holdings update')

    def anchor(e):
        """Holdings date a prose period ending `e` belongs to: `e` itself, or the single holdings date 1-7 days
        later (2025-01-06 8-K: purchases Dec 30-31, holdings as of Jan 5)."""
        if e in weekly:
            return e
        later = [h for h in weekly if 0 < (dt.date.fromisoformat(h) - dt.date.fromisoformat(e)).days <= 7]
        return later[0] if len(later) == 1 else None

    for e in sorted(set(weeks) - set(weekly)):
        a = anchor(e)
        if a is None or weeks[e].get('layout') != 'prose':
            raise UnknownLayout(f'{what}: period data for {e} without a BTC holdings figure')
        for k2, v in weeks.pop(e).items():
            if k2 != 'layout' and weekly[a].get(k2) is None:
                weekly[a][k2] = v
        notes.append(f'prose period ending {e} assigned to holdings date {a}')
    for x in inst:
        if x.period_end not in weekly and x.layout == 'prose' and (a := anchor(x.period_end)):
            notes.append(f'{x.ticker} ATM period ending {x.period_end} assigned to holdings date {a}')
            x.period_end = a
    for prog, d, v in orphan:
        t = 'MSTR' if prog in ('Sales Agreement', 'Common ATM') else prog.split()[0]
        match = [x for x in inst if x.ticker == t and x.period_end == d and x.action == 'atm_sale']
        if d in weekly and len(match) == 1 and match[0].available_usd is None:
            match[0].available_usd = v
        else:
            notes.append(f'ignored capacity sentence {prog} as of {d} (not a weekly period end)')

    bal = balances(bs)
    for e, b in bal.items():
        if e not in weekly:
            raise UnknownLayout(f'{what}: USD balance dated {e} matches no BTC holdings date')
        weekly[e].update(b)
    for e, field_, v in buyback_remaining(text, max(weekly)):
        if e not in weekly:
            notes.append(f'buyback authorization dated {e} matches no BTC holdings date; ignored')
            continue
        if weekly[e].get(field_) not in (None, v):
            raise UnknownLayout(f'{what}: two different {field_} figures for {e}: {weekly[e][field_]} and {v}')
        weekly[e][field_] = v
    for m in re.finditer(r'approved an increase in the aggregate purchase price authorized under its digital credit '
                         rf'securities repurchase program (?:\([^)]*\) )?from {MONEY} to {MONEY}', text, re.I):
        weekly[max(weekly)]['pref_buyback_authorization_increase_usd'] = money(*m.group(3, 4)) - money(*m.group(1, 2))
    for e, (b, d) in share_counts(bs, what).items():
        if e in weekly:
            weekly[e].update(basic_shares=b, assumed_diluted_shares=d)

    out = Parsed(notes=notes)
    ends = sorted(weekly)
    for i, e in enumerate(ends):
        w = dict(weekly[e])
        layout = w.pop('layout')
        start = w.pop('period_start', None)
        if start is None:
            # sub-period without its own start: day after the previous sub-period, else the instrument period
            start = next((x.period_start for x in inst if x.period_end == e and x.period_start), None)
            if start is None and i > 0:
                start = (dt.date.fromisoformat(ends[i - 1]) + dt.timedelta(days=1)).isoformat()
        out.weeks.append(Week(period_start=start, period_end=e, layout=layout, **w))
    for x in inst:
        if x.period_end not in weekly:
            raise UnknownLayout(f'{what}: {x.action} {x.ticker} for {x.period_end} matches no BTC holdings date')
    out.instruments = inst
    return out
