"""One Strategy weekly-update document (8-K body or its Exhibit 99.1) -> week rows and instrument rows. stdlib only.

Three layout families are recognised, and anything that looks like a weekly trade table but fits none of them
raises `UnknownLayout` instead of being guessed at:

  prose      Jan-Mar 2025. Sentences: "acquired approximately N bitcoins for approximately $X ...", "held an aggregate
             of approximately N bitcoins ...", "sold an aggregate of N Shares ... remained available ...".
  table      Mar 2025 onward. Period row ("During Period A to B | As of B"), a header row, then data rows. ATM rows are
             labelled "Common ATM" / "STRK ATM" (2025) or "MSTR Stock" / "STRC Stock" (2026). BTC tables carry
             period and cumulative columns in one row, or (from Oct 2026) in two separate tables.
  sentence   Weeks with no trades: "did not sell any shares", "did not purchase any bitcoin", "Strategy holds
             approximately N bitcoin".

Section finding (heading text), `num`, the "unknown label raises" rule and the USD Reserve balance sentences follow
dat-accretion `dat/parse_mstr.py`; the 2025 layouts, remaining ATM capacity, cumulative cost basis and the
share-count (KPI) table are new here.
"""
import re, datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from .html import blocks, num, key

MONTH = r'(?:January|February|March|April|May|June|July|August|September|October|November|December)'
DATE = rf'{MONTH} \d{{1,2}}, ?\d{{4}}'
SCALE = {'thousand': Decimal(10) ** 3, 'million': Decimal(10) ** 6, 'billion': Decimal(10) ** 9}
TICKERS = ('MSTR', 'STRK', 'STRF', 'STRD', 'STRC', 'STRE')
ROW_TICKER = {'Common ATM': 'MSTR', 'Common Stock ATM': 'MSTR', '2024 Common ATM': 'MSTR', '2025 Common ATM': 'MSTR'}


class UnknownLayout(ValueError):
    """A weekly-update table or sentence the parser does not recognise. Never guessed past."""


class NotWeekly(Exception):
    """The document has no weekly BTC update (other 8-K: earnings, notes, governance...)."""


@dataclass
class Week:
    period_start: str | None
    period_end: str
    layout: str
    btc_acquired: Decimal | None = None
    btc_sold: Decimal | None = None
    btc_purchase_usd: Decimal | None = None
    btc_purchase_usd_precision: Decimal | None = None
    btc_avg_purchase_price: Decimal | None = None
    btc_held: Decimal | None = None
    btc_cost_basis_usd: Decimal | None = None
    btc_cost_basis_usd_precision: Decimal | None = None
    btc_avg_cost_basis: Decimal | None = None
    usd_reserve: Decimal | None = None
    usd_cash: Decimal | None = None
    basic_shares: Decimal | None = None
    assumed_diluted_shares: Decimal | None = None
    atm_total_net_proceeds_stated: Decimal | None = None
    pref_buyback_remaining_usd: Decimal | None = None
    mstr_buyback_remaining_usd: Decimal | None = None
    pref_buyback_authorization_increase_usd: Decimal | None = None
    atm_no_sales_stated: bool = False  # 'did not sell any shares under its at-the-market offering program'


@dataclass
class Instrument:
    period_start: str | None
    period_end: str
    ticker: str
    action: str  # 'atm_sale' or 'buyback'
    layout: str
    shares: Decimal | None = None
    notional_usd: Decimal | None = None
    amount_usd: Decimal | None = None  # ATM: net proceeds; buyback: aggregate purchase price
    available_usd: Decimal | None = None  # ATM remaining capacity as of period_end
    currency: str = 'USD'
    program: str = ''  # row label or agreement name as filed, e.g. '2025 Common ATM', 'STRK ATM', 'MSTR Stock'


@dataclass
class Parsed:
    weeks: list = field(default_factory=list)
    instruments: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def iso(s):
    return dt.datetime.strptime(re.sub(r',\s*', ', ', s), '%B %d, %Y').date().isoformat()


def norm(t):
    """Undo glued words in 2025 tables: 'During PeriodMarch 24' -> 'During Period March 24', 'As ofMay 4'."""
    t = re.sub(rf'(Period|of|to)(?={MONTH})', r'\1 ', t)
    t = re.sub(r'(forIssuance)', 'for Issuance', t)
    return ' '.join(t.split())


def money(amount, unit):
    return Decimal(amount.replace(',', '')) * SCALE[unit.lower()]


def ulp(amount, unit_scale):
    """Value of one unit in the last disclosed digit, in USD."""
    return Decimal(1).scaleb(Decimal(amount.replace(',', '')).as_tuple().exponent) * unit_scale


# ---------------------------------------------------------------- sections

HEADINGS = {
    'atm': r'(?:Common Stock |Preferred Stock |STR[A-Z] Preferred Stock )?ATMs?(?: Updates?)?',
    'btc': r'(?:BTC|Bitcoin Holdings) Updates?',
    'atm+btc': rf'(?:Common Stock )?ATM and BTC Updates?(?: for the Period {DATE} to {DATE})?',
    'repurchase': r'(?:Share )?Repurchase Program Updates?',
    'usd': r'USD Reserve(?: and USD Cash)? Updates?',
}
TRADE_HEADER = re.compile(r'^(?:BTC ?(?:Acquired|Purchased|Sold|Purchased/\(Sold\))|Shares Sold|Shares Repurchased)',
                          re.I)


def is_heading(t):
    return (len(t) < 110 and t[:1].isupper() and '$' not in t and ':' not in t
            and not t.endswith(('.', ';', ',')) and not re.match(r'\(\d+\)|\*', t))


def sections(bs):
    """[(kind, [blocks])] for recognised headings, plus [(None, [blocks])] runs elsewhere."""
    out, cur = [(None, [])], None
    for k, v in bs:
        if k == 'p' and is_heading(v):
            cur = next((n for n, rx in HEADINGS.items() if re.fullmatch(rx, v)), None)
            out.append((cur, []))
            continue
        out[-1][1].append((k, v))
    return out


# ---------------------------------------------------------------- tables

def period_of(text):
    """'During Period A to B' / 'As of B' anywhere in a cell -> (start, end) or None."""
    text = norm(text)
    if m := re.search(rf'During (?:the )?Period ({DATE}) (?:to|through) ({DATE})', text):
        return iso(m.group(1)), iso(m.group(2))
    if m := re.search(rf'As of ({DATE})', text):
        return None, iso(m.group(1))
    return None


def cell_amount(cell, header_scale, what):
    """'$1.20 billion' / '1.92 billion' / '18,111.0' (header in millions) / '$ 22.0 (3)' -> (USD, precision)."""
    c = norm(cell)
    c = re.sub(r'\s*(?:of )?(?:MSTR|STR[A-Z])? ?Shares$', '', c)
    c = re.sub(r'(\s*\(\d\))+$', '', c).replace('$', '').replace('*', '').strip()
    if c in ('-', '—', '–', ''):
        return Decimal(0), None
    if m := re.fullmatch(r'([\d,]+(?:\.\d+)?) (million|billion)', c):
        return money(*m.groups()), ulp(m.group(1), SCALE[m.group(2)])
    if not re.fullmatch(r'[\d,]+(?:\.\d+)?', c):
        raise UnknownLayout(f'{what}: not an amount: {cell!r}')
    if header_scale is None:
        raise UnknownLayout(f'{what}: amount {cell!r} has no unit in cell or header')
    return Decimal(c.replace(',', '')) * header_scale, ulp(c, header_scale)


def header_scale(label):
    m = re.search(r'\(in (thousands|millions|billions)\)', label, re.I)
    return SCALE[m.group(1).lower().rstrip('s')] if m else None


def shares_cell(cell, what):
    c = re.sub(r'\s*(?:MSTR|STR[A-Z]) ?Shares$', '', norm(cell))
    try:
        return num(c)
    except ValueError:
        raise UnknownLayout(f'{what}: not a share count: {cell!r}') from None
