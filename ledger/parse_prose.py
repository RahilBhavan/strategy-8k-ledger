"""Prose balances, trades and share-count readers."""
from .parse_types import *

P_BUY = re.compile(rf'during the period between ({DATE}) and ({DATE}), (?:the Company|Strategy) acquired approximately '
                   r'([\d,]+) bitcoins? for approximately \$([\d,.]+) (million|billion) in cash, at an average price of '
                   r'approximately \$([\d,]+) per bitcoin')
P_NOBUY = re.compile(rf'during the period between ({DATE}) and ({DATE}),[^.]*?did not purchase any bitcoin')
P_HELD = re.compile(rf'As of ({DATE}), (?:the Company|Strategy|MicroStrategy), together with its subsidiaries, held an '
                    r'aggregate of approximately ([\d,]+) bitcoins?, which were acquired at an aggregate purchase price of '
                    r'approximately \$([\d,.]+) (million|billion) and an average purchase price of approximately '
                    r'\$([\d,]+) per bitcoin')
P_HOLDS = re.compile(rf'As of ({DATE}), Strategy (?:holds|held) (?:an aggregate of )?approximately ([\d,]+) bitcoins?'
                     r'(?:,? (?:that were |which were )?acquired (?:for|at) (?:an aggregate (?:purchase price )?of )?'
                     r'(?:approximately )?\$([\d,.]+) (billion|million)'
                     r'(?:,? (?:at|and) an average (?:purchase )?price of (?:approximately )?\$([\d,.]+) per bitcoin)?)?')
P_SOLD = re.compile(rf'during the period between ({DATE}) and ({DATE}), (?:the Company|Strategy) had sold an aggregate of '
                    r'([\d,]+) (MSTR |STR[A-Z] )?Shares under the (Sales Agreement|Common ATM|STR[A-Z] ATM),? for aggregate '
                    r'net proceeds to the Company \(less sales commissions\) of approximately \$([\d,.]+) (million|billion)'
                    r'|during the period between ' rf'({DATE}) and ({DATE}), (?:the Company|Strategy) sold an aggregate of '
                    r'([\d,]+) (MSTR |STR[A-Z] )?Shares under the (Sales Agreement|Common ATM|STR[A-Z] ATM),? for aggregate '
                    r'net proceeds to the Company \(less sales commissions\) of approximately \$([\d,.]+) (million|billion)')
P_AVAIL = re.compile(rf'As of ({DATE}), approximately \$([\d,.]+) (million|billion) of (MSTR |STR[A-Z] )?Shares remained '
                     r'available for issuance and sale pursuant to the (Sales Agreement|Common ATM|STR[A-Z] ATM)')
P_NOSELL = re.compile(rf'during the period between ({DATE}) and ({DATE}),[^.]*?did not (?:make any sales|sell any shares) of '
                      r'class A common stock')


def prose(text, what):
    """Doc-wide sentences -> (weeks {end: Week fields}, instruments). Sentences that look like updates but do not
    match a known pattern raise."""
    weeks, inst = {}, []
    for m in P_BUY.finditer(text):
        s, e = iso(m.group(1)), iso(m.group(2))
        weeks.setdefault(e, {}).update(period_start=s, btc_acquired=Decimal(m.group(3).replace(',', '')),
                                       btc_purchase_usd=money(m.group(4), m.group(5)),
                                       btc_purchase_usd_precision=ulp(m.group(4), SCALE[m.group(5)]),
                                       btc_avg_purchase_price=Decimal(m.group(6).replace(',', '')))
    for m in P_NOBUY.finditer(text):
        s, e = iso(m.group(1)), iso(m.group(2))
        weeks.setdefault(e, {}).update(period_start=s, btc_acquired=Decimal(0))
    for m in P_HELD.finditer(text):
        e = iso(m.group(1))
        weeks.setdefault(e, {}).update(btc_held=Decimal(m.group(2).replace(',', '')),
                                       btc_cost_basis_usd=money(m.group(3), m.group(4)),
                                       btc_cost_basis_usd_precision=ulp(m.group(3), SCALE[m.group(4)]),
                                       btc_avg_cost_basis=Decimal(m.group(5).replace(',', '')))
    n_buy = len(re.findall(r'bitcoins? for approximately \$', text))
    if n_buy != len(P_BUY.findall(text)):
        raise UnknownLayout(f'{what}: a bitcoin-purchase sentence does not match the known prose pattern')
    if len(re.findall(r'held an aggregate of approximately', text)) != len(P_HELD.findall(text)):
        raise UnknownLayout(f'{what}: a holdings sentence does not match the known prose pattern')
    avail = {}
    for m in P_AVAIL.finditer(text):
        avail.setdefault(m.group(5), []).append((iso(m.group(1)), money(m.group(2), m.group(3))))
    for m in P_SOLD.finditer(text):
        g = m.groups()
        g = g[:7] if g[0] else g[7:]
        s, e = iso(g[0]), iso(g[1])
        prog = g[4]
        t = 'MSTR' if prog in ('Sales Agreement', 'Common ATM') else prog.split()[0]
        # the capacity sentence can be dated a few days after the sale period (2025-01-06: sales to Dec 31,
        # capacity as of Jan 5); take the earliest capacity date on or after the sale period end, within 7 days
        cands = sorted(a for a in avail.get(prog, []) if 0 <= (dt.date.fromisoformat(a[0]) - dt.date.fromisoformat(e)).days <= 7)
        if not cands:
            raise UnknownLayout(f'{what}: ATM sale under {prog} without a matching "remained available" sentence')
        avail[prog].remove(cands[0])
        inst.append(Instrument(s, e, t, 'atm_sale', 'prose', shares=Decimal(g[2].replace(',', '')),
                               amount_usd=money(g[5], g[6]), available_usd=cands[0][1], program=prog))
    if len(re.findall(r'sold an aggregate of [\d,]+', text)) != len(P_SOLD.findall(text)):
        raise UnknownLayout(f'{what}: an ATM sale sentence does not match the known prose pattern')
    for m in P_NOSELL.finditer(text):
        s, e = iso(m.group(1)), iso(m.group(2))
        if not any(i.ticker == 'MSTR' and i.period_end == e for i in inst):
            inst.append(Instrument(s, e, 'MSTR', 'atm_sale', 'prose', shares=Decimal(0), amount_usd=Decimal(0),
                                   program='Common ATM'))
    # capacity sentences with no sale sentence: returned for parse_document to attach to a matching week, or ignore
    orphan = [(prog, d, v) for prog, lst in avail.items() for d, v in lst]
    return weeks, inst, orphan


# ---------------------------------------------------------------- USD Reserve / Cash

MONEY = r'\$([\d,.]+) (million|billion)'
BAL_ONE = rf'As of ({DATE}), the balance of the USD Reserve (?:is|was) {MONEY}'
BAL_TWO = rf'As of ({DATE}), the balances of the USD Reserve and USD Cash were {MONEY} and {MONEY}'
BAL_ITEM = rf'USD (Reserve|Cash): {MONEY}'


def balances(bs):
    out, pending = {}, None
    for k, t in bs:
        if k != 'p':
            continue
        if m := re.search(BAL_ONE, t, re.I):
            out.setdefault(iso(m.group(1)), {})['usd_reserve'] = money(*m.group(2, 3))
        elif m := re.search(BAL_TWO, t):
            d = out.setdefault(iso(m.group(1)), {})
            d['usd_reserve'], d['usd_cash'] = money(*m.group(2, 3)), money(*m.group(4, 5))
        elif m := re.search(rf'As of ({DATE}), the balances of the USD Reserve and USD Cash were as follows', t):
            pending = iso(m.group(1))
        elif pending and (m := re.fullmatch(BAL_ITEM, t)):
            out.setdefault(pending, {})['usd_' + m.group(1).lower()] = money(*m.group(2, 3))
    return out


# ---------------------------------------------------------------- buyback authorization remaining

APOS = "[\u2019']"
P_REMAINS = re.compile(rf'\$([\d,.]+) (million|billion) aggregate purchase price of (?:Strategy{APOS}s )?'
                       rf'(preferred stock|class A common stock|MSTR Stock) remains available under [^.]*?'
                       rf'(?:as of (?:each of )?({DATE})(?: and ({DATE}))?)?\.')
P_REMAINED = re.compile(rf'As of ({DATE}), (?:after giving effect to the increase, )?\$([\d,.]+) (million|billion) '
                        rf'aggregate purchase price remained available under (?:the |Strategy{APOS}s |its )?'
                        r'(digital credit securities repurchase program|Digital Credit Securities Repurchase Program|'
                        r'MSTR Stock repurchase program)')


def buyback_remaining(text, default_end):
    """[(as_of, field, USD)] for 'remains available under the ... repurchase program' statements. A statement with
    no date of its own applies to the document's last period end."""
    out = []
    for m in P_REMAINS.finditer(text):
        f = 'pref_buyback_remaining_usd' if m.group(3) == 'preferred stock' else 'mstr_buyback_remaining_usd'
        dates = [iso(x) for x in m.group(4, 5) if x] or [default_end]
        out += [(e, f, money(m.group(1), m.group(2))) for e in dates]
    for m in P_REMAINED.finditer(text):
        f = 'mstr_buyback_remaining_usd' if m.group(4).startswith('MSTR') else 'pref_buyback_remaining_usd'
        out.append((iso(m.group(1)), f, money(m.group(2), m.group(3))))
    if len(re.findall(r'remains? available under', text)) > len(P_REMAINS.findall(text)) + \
            len([x for x in re.findall(r'remained available under[^.]*repurchase program', text, re.I)]):
        raise UnknownLayout('a "remains available under" buyback statement does not match the known patterns')
    return out


# ---------------------------------------------------------------- share counts (KPI table)

def share_counts(bs, what):
    """Company KPI table 'Basic Shares Outstanding' / 'Assumed Diluted Shares Outstanding' (in '000s) ->
    {as_of: (basic, diluted)}. Column dates are M/D/YYYY in the first row."""
    out = {}
    for k, t in bs:
        if k != 'table' or not any(r and r[0].startswith('Basic Shares Outstanding') for r in t):
            continue
        hdr = next((r for r in t if all(re.fullmatch(r'\d{1,2}/\d{1,2}/\d{4}', c) for c in r)), None)
        if hdr is None:
            raise UnknownLayout(f'{what}: share-count table without a date header row')
        if not any('in ‘000s' in ' '.join(r) or "in '000s" in ' '.join(r) or 'in thousands' in ' '.join(r).lower()
                   for r in t):
            raise UnknownLayout(f"{what}: share-count table without an (in '000s) label")
        dates = [dt.datetime.strptime(c, '%m/%d/%Y').date().isoformat() for c in hdr]
        basic = next(r for r in t if r[0].startswith('Basic Shares Outstanding'))
        dil = [r for r in t if r[0].startswith('Assumed Diluted Shares Outstanding')]
        for i, d in enumerate(dates):
            b = num(basic[1 + i]) * 1000 if len(basic) == len(dates) + 1 else None
            out[d] = (b, None)
        # diluted row can sit in a continuation table; search the whole document for it
        if not dil:
            for k2, t2 in bs:
                if k2 == 'table':
                    dil += [r for r in t2 if r[0].startswith('Assumed Diluted Shares Outstanding')]
        if dil and len(dil[0]) == len(dates) + 1:
            for i, d in enumerate(dates):
                out[d] = (out[d][0], num(re.sub(r'\(\d\)$', '', dil[0][1 + i])) * 1000)
    return out


# ---------------------------------------------------------------- document
