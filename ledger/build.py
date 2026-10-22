"""Fetch every Strategy 8-K since 2025-01-01, parse the weekly updates, write data/weekly.csv,
data/instrument_weekly.csv and data/filings.csv. `python -m ledger build [--refresh]`."""
import csv, os, re
from decimal import Decimal
from . import edgar
from .parse import parse_document, NotWeekly, UnknownLayout, Week, Instrument

DATA = os.path.join(edgar.ROOT, 'data')
SINCE = '2025-01-01'

WEEK_FIELDS = ['accession', 'form', 'filed', 'doc_url', 'doc_role', 'fetched_utc', 'period_start', 'period_end',
               'layout', 'btc_acquired', 'btc_sold', 'btc_purchase_usd', 'btc_purchase_usd_precision',
               'btc_avg_purchase_price', 'btc_held', 'btc_cost_basis_usd', 'btc_cost_basis_usd_precision',
               'btc_avg_cost_basis', 'atm_net_proceeds_usd', 'atm_total_net_proceeds_stated', 'atm_no_sales_stated', 'buyback_usd', 'pref_buyback_remaining_usd',
               'mstr_buyback_remaining_usd', 'pref_buyback_authorization_increase_usd',
               'usd_reserve', 'usd_cash', 'basic_shares', 'assumed_diluted_shares']
INST_FIELDS = ['accession', 'form', 'filed', 'doc_url', 'doc_role', 'period_start', 'period_end', 'ticker', 'action',
               'program', 'currency', 'shares', 'notional_usd', 'amount_usd', 'available_usd', 'layout']
FILING_FIELDS = ['accession', 'form', 'filed', 'items', 'url', 'status', 'doc_url', 'weeks', 'note']

INCORPORATED = re.compile(r'(?:filed|furnished) (?:herewith )?as Exhibit 99\.1', re.I)


def fmt(v):
    if v is None:
        return ''
    d = Decimal(v)
    if d == d.to_integral():
        return str(d.quantize(Decimal(1)))
    return format(d.normalize(), 'f')


def exhibit_991(filing):
    """URL of the filing's EX-99.1 document, or None."""
    for item in edgar.filing_index(filing['folder']):
        name = item['name']
        if re.search(r'ex[-_]?99[-_]?0?1\b|ex991\b|dex991', name, re.I) and name.lower().endswith('.htm'):
            return f"{filing['folder']}/{name}"
    return None


def parse_filing(f):
    """-> (doc_url, doc_role, Parsed). Tries the 8-K body; if it has no weekly update and points to Exhibit 99.1,
    tries the exhibit (Strategy moved the weekly tables into Exhibit 99.1 on 2026-10-13)."""
    body = edgar.fetch_text(f['url'])
    where = f"{f['accession']} ({f['url']})"
    try:
        return f['url'], '8-K body', parse_document(body, where)
    except NotWeekly:
        if '9.01' not in f['items'] or not INCORPORATED.search(body):
            raise
    url = exhibit_991(f)
    if url is None:
        raise NotWeekly('no weekly update in body and no EX-99.1 document')
    return url, 'EX-99.1', parse_document(edgar.fetch_text(url), f"{f['accession']} ({url})")


def normalize_filing(f, url, role, p):
    """Normalize one parsed filing without selecting or publishing revisions."""
    weeks, insts = [], []
    base = {'accession': f['accession'], 'form': f['form'], 'filed': f['filed'], 'doc_url': url, 'doc_role': role}
    for w in p.weeks:
        atm = [i for i in p.instruments if i.action == 'atm_sale' and i.period_end == w.period_end]
        bb = [i for i in p.instruments if i.action == 'buyback' and i.period_end == w.period_end]
        row = dict(base, fetched_utc=edgar.fetched_at(url), **{k: getattr(w, k) for k in Week.__dataclass_fields__})
        row['atm_net_proceeds_usd'] = sum((i.amount_usd or 0 for i in atm if i.currency == 'USD'), Decimal(0)) \
            if atm else (Decimal(0) if w.atm_no_sales_stated else None)
        row['buyback_usd'] = sum((i.amount_usd or 0 for i in bb if i.currency == 'USD'), Decimal(0)) if bb else None
        weeks.append(row)
    for i in p.instruments:
        start = i.period_start or next((w.period_start for w in p.weeks if w.period_end == i.period_end), None)
        insts.append(dict(base, **{k: getattr(i, k) for k in Instrument.__dataclass_fields__ if k != 'period_start'},
                          period_start=start))
    return weeks, insts


def build(refresh=False):
    filings = edgar.filings(since=SINCE, refresh=refresh)
    weeks, insts, log = [], [], []
    period_sources = {}
    for f in filings:
        try:
            url, role, p = parse_filing(f)
        except NotWeekly as e:
            log.append(dict(f, status='not_weekly', doc_url='', weeks='', note=str(e)))
            continue
        for w in p.weeks:
            if w.period_end in period_sources:
                raise UnknownLayout(f'duplicate economic period {w.period_end}: '
                                    f'{period_sources[w.period_end]} and {f["accession"]}; '
                                    'review amendment/restatement before rebuilding')
            period_sources[w.period_end] = f['accession']
        filing_weeks, filing_insts = normalize_filing(f, url, role, p)
        weeks.extend(filing_weeks)
        insts.extend(filing_insts)
        log.append(dict(f, status='weekly', doc_url=url, weeks=';'.join(w.period_end for w in p.weeks),
                        note='; '.join(p.notes)))
    weeks.sort(key=lambda r: (r['period_end'], r['filed'], r['accession']))
    insts.sort(key=lambda r: (r['period_end'], r['action'], r['ticker'], r['accession']))
    write(os.path.join(DATA, 'weekly.csv'), WEEK_FIELDS, weeks)
    write(os.path.join(DATA, 'instrument_weekly.csv'), INST_FIELDS, insts)
    write(os.path.join(DATA, 'filings.csv'), FILING_FIELDS, log)
    print(f"8-Ks read {len(filings)}; weekly {sum(r['status'] == 'weekly' for r in log)}; "
          f"weekly.csv {len(weeks)} rows; instrument_weekly.csv {len(insts)} rows")
    return weeks, insts


def write(path, fields, rows):
    with open(path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fields, extrasaction='ignore', lineterminator='\n')
        w.writeheader()
        for r in rows:
            w.writerow({k: ('true' if v else 'false') if isinstance(v, bool) else fmt(v) if isinstance(v, (Decimal, int)) else
                        ('' if v is None else v) for k, v in r.items() if k in fields})


def read(name):
    with open(os.path.join(DATA, name), newline='') as fh:
        return list(csv.DictReader(fh))
