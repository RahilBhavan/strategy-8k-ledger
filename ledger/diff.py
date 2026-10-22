"""What changed in the latest weekly 8-K versus the week before, from data/*.csv."""
from decimal import Decimal as D
from . import build


def d(v):
    return None if v in (None, '') else D(v)


def usd(v):
    if v is None:
        return '-'
    a = abs(v)
    s = f'${a / 10**9:,.2f}B' if a >= 10**9 else f'${a / 10**6:,.1f}M' if a >= 10**5 else f'${a:,.0f}'
    return ('-' if v < 0 else '') + s


def signed(v, f=usd):
    if v is None:
        return 'n/a'
    return ('+' if v > 0 else '') + (f(v) if v >= 0 else '-' + f(-v))


def num(v):
    return '-' if v is None else f'{v:,.0f}'


def diff(accession=None, weeks=None, insts=None, checks=None):
    weeks = weeks if weeks is not None else build.read('weekly.csv')
    insts = insts if insts is not None else build.read('instrument_weekly.csv')
    if accession is None:
        accession = max(weeks, key=lambda w: (w['filed'], w['period_end']))['accession']
    mine = [w for w in weeks if w['accession'] == accession]
    if not mine:
        raise SystemExit(f'no weekly rows for accession {accession}')
    cur = mine[-1]
    idx = weeks.index(cur)
    prev = weeks[idx - len(mine)] if idx - len(mine) >= 0 else None
    lines = [f"Strategy weekly 8-K {accession}, filed {cur['filed']}",
             f"  source: {cur['doc_url']} ({cur['doc_role']})",
             f"  period: {mine[0]['period_start']} to {cur['period_end']}"
             + (f" ({len(mine)} sub-periods)" if len(mine) > 1 else '')]
    if prev is None:
        lines.append('  no earlier week in the ledger to compare with')
        return '\n'.join(lines)
    lines.append(f"  compared with: week ending {prev['period_end']} (8-K {prev['accession']}, filed {prev['filed']})")
    acq = sum(d(w['btc_acquired']) or D(0) for w in mine)
    sold = sum(d(w['btc_sold']) or D(0) for w in mine)
    spent = sum(d(w['btc_purchase_usd']) or D(0) for w in mine if d(w['btc_acquired']))
    held, pheld = d(cur['btc_held']), d(prev['btc_held'])
    lines += ['', 'Bitcoin',
              f"  held          {num(pheld)} -> {num(held)} BTC ({signed(held - pheld, num)})",
              f"  acquired      {num(acq)} BTC for {usd(spent)}" + (f"; sold {num(sold)} BTC" if sold else '')]
    for w in mine:
        if d(w['btc_avg_purchase_price']):
            lines.append(f"    {w['period_end']}: average {usd(d(w['btc_avg_purchase_price']))} per BTC")
    roll = pheld + acq - sold
    lines.append(f"  roll check    {num(pheld)} + {num(acq)} - {num(sold)} = {num(roll)}; stated {num(held)}"
                 + (' OK' if roll == held else f' (residual {signed(held - roll, num)} BTC)'))
    cb, pcb = d(cur['btc_cost_basis_usd']), d(prev['btc_cost_basis_usd'])
    lines.append(f"  cost basis    {usd(pcb)} -> {usd(cb)}; average {usd(d(prev['btc_avg_cost_basis']))} -> "
                 f"{usd(d(cur['btc_avg_cost_basis']))} per BTC")
    for f, label in (('usd_reserve', 'USD Reserve'), ('usd_cash', 'USD Cash')):
        a, b = d(prev[f]), d(cur[f])
        if a is not None or b is not None:
            lines.append(f"  {label:<13} {usd(a)} -> {usd(b)} ({signed(b - a) if a is not None and b is not None else 'n/a'})")

    def by_ticker(acc, ends, action):
        out = {}
        for i in insts:
            if i['accession'] == acc and i['period_end'] in ends and i['action'] == action:
                o = out.setdefault(i['ticker'], {'shares': D(0), 'amount': D(0), 'available': None})
                o['shares'] += d(i['shares']) or D(0)
                o['amount'] += d(i['amount_usd']) or D(0)
                o['available'] = d(i['available_usd']) if d(i['available_usd']) is not None else o['available']
        return out

    pmine = [w for w in weeks if w['accession'] == prev['accession']]
    now = by_ticker(accession, {w['period_end'] for w in mine}, 'atm_sale')
    then = by_ticker(prev['accession'], {w['period_end'] for w in pmine}, 'atm_sale')
    lines += ['', 'ATM sales (net proceeds; capacity = remaining "available for issuance and sale")']
    if not now:
        lines.append('  no ATM table' + (' (8-K states no ATM sales)' if cur['atm_no_sales_stated'] == 'true' else ''))
    for t in sorted(set(now) | set(then)):
        n, p = now.get(t), then.get(t)
        if n is None:
            lines.append(f"  {t:<5} not in this week's table (was in the prior one)")
            continue
        cap = f"capacity {usd(p['available'] if p else None)} -> {usd(n['available'])}"
        if p and p['available'] is not None and n['available'] is not None:
            cap += f" ({signed(n['available'] - p['available'])})"
        tag = '' if p else '  NEW in table'
        lines.append(f"  {t:<5} sold {num(n['shares'])} shares for {usd(n['amount'])}; {cap}{tag}")
    bb = by_ticker(accession, {w['period_end'] for w in mine}, 'buyback')
    if bb:
        lines += ['', 'Buybacks (aggregate purchase price)']
        for t in sorted(bb):
            if bb[t]['shares']:
                lines.append(f"  {t:<5} {num(bb[t]['shares'])} shares for {usd(bb[t]['amount'])}")
        if not any(v['shares'] for v in bb.values()):
            lines.append('  none')
    if checks is not None:
        flagged = [c for c in checks if c['accession'] == accession and c['status'] != 'OK']
        lines += ['', 'Consistency checks for this filing: ' + ('all OK' if not flagged else '')]
        lines += [f"  {c['check']}: {c['status']} {c['note']}" for c in flagged]
    if cur['layout'] != prev['layout']:
        lines += ['', f"Layout changed: {prev['layout']} -> {cur['layout']}"]
    if cur['doc_role'] != prev['doc_role']:
        lines += [f"Document changed: tables now in {cur['doc_role']} (was {prev['doc_role']})"]
    return '\n'.join(lines)
