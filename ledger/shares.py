"""Basic share count and sats per share, week by week. stdlib only.

Share count used: BASIC = class A + class B common shares outstanding, as printed on the cover page of each 10-Q and
10-K ("As of <date>, the registrant had X and Y shares of class A common stock and class B common stock
outstanding"). Between cover dates the count is rolled forward with the weekly 8-K figures:

    basic(week) = basic(latest cover date on or before the week's end)
                  + MSTR shares sold under the ATM in weeks ending after that cover date
                  - MSTR shares repurchased in those weeks

This is a reconstruction (an assumption-labelled model, not a filed figure). It misses shares from option exercises,
RSU vesting, note or preferred conversions and any stock dividends, and it attributes a whole week's ATM sales to
one side of a mid-week cover date. `residuals()` measures the miss at each next cover date.

Strategy's own KPI uses "Assumed Diluted Shares Outstanding" (company-defined, non-GAAP: basic plus every share from
assumed conversion of notes and convertible preferred, options and unvested awards). The weekly 8-Ks printed that
figure only from January to February 2025, so it is kept as a column in weekly.csv but not modelled weekly here.
"""
import json, re
from decimal import Decimal as D
from . import edgar, build
from .html import blocks

COVER = re.compile(r'As of ([A-Z][a-z]+ \d{1,2}, \d{4}), the registrant had ([\d,]+) and ([\d,]+) shares of class A '
                   r'common stock and class B common stock outstanding, respectively')
ANCHOR_FIELDS = ['as_of', 'class_a', 'class_b', 'basic', 'form', 'accession', 'filed', 'doc_url', 'definition']
SATS_FIELDS = ['period_end', 'btc_held', 'basic_shares_est', 'anchor_as_of', 'anchor_url', 'mstr_atm_shares_since_anchor',
               'mstr_buyback_shares_since_anchor', 'sats_per_basic_share', 'method']
SINCE = '2024-10-01'


def anchors(refresh=False):
    """Cover-page counts from every 10-Q/10-K filed since 2024-10-01."""
    from .parse import iso
    recent = json.loads(edgar.fetch(edgar.submissions_url(), refresh=refresh))['filings']['recent']
    out = []
    for i, form in enumerate(recent['form']):
        if form not in ('10-Q', '10-K') or recent['filingDate'][i] < SINCE:
            continue
        acc = recent['accessionNumber'][i]
        url = f"https://www.sec.gov/Archives/edgar/data/1050446/{acc.replace('-', '')}/{recent['primaryDocument'][i]}"
        text = ' '.join(v for k, v in blocks(edgar.fetch_text(url))[:400] if k == 'p')
        m = COVER.search(text)
        if not m:
            raise ValueError(f'{url}: cover-page share sentence not found (layout changed?)')
        a, b = D(m.group(2).replace(',', '')), D(m.group(3).replace(',', ''))
        out.append({'as_of': iso(m.group(1)), 'class_a': a, 'class_b': b, 'basic': a + b, 'form': form,
                    'accession': acc, 'filed': recent['filingDate'][i], 'doc_url': url,
                    'definition': 'cover page: class A + class B shares outstanding'})
    out.sort(key=lambda r: r['as_of'])
    build.write(build.os.path.join(build.DATA, 'share_anchors.csv'), ANCHOR_FIELDS, out)
    return out


def _flows(insts):
    """{period_end: (MSTR ATM shares sold, MSTR shares repurchased)} summed over filings."""
    out = {}
    for i in insts:
        if i['ticker'] != 'MSTR' or not i['shares']:
            continue
        sold, bought = out.get(i['period_end'], (D(0), D(0)))
        if i['action'] == 'atm_sale':
            sold += D(i['shares'])
        elif i['action'] == 'buyback':
            bought += D(i['shares'])
        out[i['period_end']] = (sold, bought)
    return out


def estimate(weeks, insts, anchor_rows):
    flows = _flows(insts)
    ends = sorted({w['period_end'] for w in weeks})
    held = {w['period_end']: D(w['btc_held']) for w in weeks}
    first = min(w['period_start'] or w['period_end'] for w in weeks)
    usable = [a for a in anchor_rows if a['as_of'] >= first]  # earlier anchors would miss unparsed ATM weeks
    out = []
    for e in ends:
        anc = [a for a in usable if a['as_of'] <= e]
        if not anc:
            continue
        a = anc[-1]
        sold = sum((flows.get(x, (D(0), D(0)))[0] for x in ends if a['as_of'] < x <= e), D(0))
        bought = sum((flows.get(x, (D(0), D(0)))[1] for x in ends if a['as_of'] < x <= e), D(0))
        basic = D(a['basic']) + sold - bought
        out.append({'period_end': e, 'btc_held': held[e], 'basic_shares_est': basic, 'anchor_as_of': a['as_of'],
                    'anchor_url': a['doc_url'], 'mstr_atm_shares_since_anchor': sold,
                    'mstr_buyback_shares_since_anchor': bought,
                    'sats_per_basic_share': (held[e] * D(10) ** 8 / basic).quantize(D('0.01')),
                    'method': 'model: cover-page basic count + weekly MSTR ATM shares - MSTR buybacks'})
    return out


def residuals(weeks, insts, anchor_rows):
    """At each cover date after the first: rolled-forward estimate (from the previous anchor) vs the filed count."""
    flows = _flows(insts)
    ends = sorted({w['period_end'] for w in weeks})
    out = []
    for prev, nxt in zip(anchor_rows, anchor_rows[1:]):
        if prev['as_of'] < ends[0]:
            continue
        span = [x for x in ends if prev['as_of'] < x <= nxt['as_of']]
        sold = sum((flows.get(x, (D(0), D(0)))[0] for x in span), D(0))
        bought = sum((flows.get(x, (D(0), D(0)))[1] for x in span), D(0))
        est = D(prev['basic']) + sold - bought
        out.append({'from': prev['as_of'], 'to': nxt['as_of'], 'estimated': est, 'filed': D(nxt['basic']),
                    'miss': D(nxt['basic']) - est, 'miss_pct': ((D(nxt['basic']) - est) / D(nxt['basic']) * 100)
                    .quantize(D('0.01'))})
    return out


def run(refresh=False):
    weeks, insts = build.read('weekly.csv'), build.read('instrument_weekly.csv')
    anc = anchors(refresh)
    est = estimate(weeks, insts, anc)
    build.write(build.os.path.join(build.DATA, 'sats_per_share.csv'), SATS_FIELDS, est)
    return anc, est, residuals(weeks, insts, anc)
