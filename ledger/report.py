"""Offline, pinned-input reports; no revision precedence or publication writes."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path

from . import build, edgar, evidence
from .parse import NotWeekly, parse_document

WEEK_NUMBERS = set(build.WEEK_FIELDS[9:]) - {'atm_no_sales_stated'}
INSTRUMENT_NUMBERS = {'shares', 'notional_usd', 'amount_usd', 'available_usd'}
RATIO = 'sats_per_basic_share'


def verify_inputs():
    """Attest report inputs against the reviewed contract, not a mutable manifest."""
    root = Path(edgar.ROOT)
    contract = json.loads((root / 'data/contract.json').read_text())
    for name in ('weekly', 'instrument_weekly', 'filings', 'manifest'):
        path = Path(edgar.MANIFEST) if name == 'manifest' else Path(build.DATA) / (name + '.csv')
        if hashlib.sha256(path.read_bytes()).hexdigest() != contract['tables'][name]['sha256']:
            raise ValueError(f'{name}: snapshot bytes differ; restore reviewed inputs')
    return contract['schema_version']


def select(period, accession=None, ticker=None, action=None, program=None):
    """Select exactly one row. Accession mode replays original cached filing bytes."""
    if accession:
        filings = [r for r in build.read('filings.csv') if r['accession'] == accession]
        if len(filings) != 1:
            raise ValueError(f'filing unavailable or ambiguous: {accession}')
        f = filings[0]
        url = f['doc_url'] or f['url']
        body, _ = evidence.source_lines(url)
        role = '8-K body' if url == f['url'] else 'EX-99.1'
        try:
            parsed = parse_document(body.decode('utf-8', errors='replace'), accession)
        except NotWeekly as e:
            raise ValueError(f'filing has no weekly observations: {accession}: {e}') from e
        weeks, instruments = build.normalize_filing(f, url, role, parsed)
        # Use the same string serialization as published CSVs, without writing them.
        def serialize(row):
            return {k: ('true' if v else 'false') if isinstance(v, bool) else
                    '' if v is None else build.fmt(v) if isinstance(v, (Decimal, int)) else v
                    for k, v in row.items()}
        rows = [serialize(r) for r in (instruments if ticker else weeks)]
    else:
        rows = build.read('instrument_weekly.csv' if ticker else 'weekly.csv')
    rows = [r for r in rows if r['period_end'] == period
            and (ticker is None or r['ticker'] == ticker)
            and (action is None or r.get('action') == action)
            and (program is None or r.get('program') == program)]
    if len(rows) != 1:
        raise ValueError(f'expected one observation, found {len(rows)} for {period}; '
                         'select accession/ticker/action/program explicitly')
    return rows[0]


def trace(row, field):
    """Trace a numeric field. Missingness is explicit; ratios never borrow shares."""
    allowed = INSTRUMENT_NUMBERS if 'ticker' in row else WEEK_NUMBERS | {RATIO}
    if field not in allowed:
        raise ValueError(f'unsupported numeric field: {field}')
    identity = {k: row[k] for k in ('accession', 'form', 'filed', 'period_start', 'period_end',
                                   'doc_url', 'doc_role', 'ticker', 'action', 'program', 'currency') if k in row}
    if field == RATIO:
        if not row.get('basic_shares') or Decimal(row['basic_shares']) <= 0:
            raise ValueError('same-date filed basic-share denominator unavailable; model refused')
        citations = [evidence.cite(row, f) for f in ('btc_held', 'basic_shares')]
        value = format(Decimal(row['btc_held']) * 100_000_000 / Decimal(row['basic_shares']), 'f')
        derivation = 'btc_held * 100000000 / same-date filed basic_shares; arithmetic precision only'
    else:
        value = row[field] or None
        citations = [evidence.cite(row, field)] if value is not None else []
        derivation = evidence.DERIVED.get(field, 'parser extraction; rounded source precision')
    return {'field': field, 'value': value, 'status': 'missing' if value is None else 'available',
            'observation': identity, 'source_fetched_utc': edgar.fetched_at(row['doc_url']),
            'derivation': derivation, 'evidence': citations}


def compare(before, after, field):
    """Keep both observations and mark revision conflicts without choosing a winner."""
    left, right = trace(before, field), trace(after, field)
    same_date = before['period_end'] == after['period_end']
    revision = same_date and before['accession'] != after['accession']
    if left['value'] is None or right['value'] is None:
        status, delta = 'missing', None
    else:
        delta = format(Decimal(right['value']) - Decimal(left['value']), 'f')
        changed = Decimal(left['value']) != Decimal(right['value'])
        status = 'conflict' if revision and changed else 'changed' if changed else 'unchanged'
    return {'kind': 'revision_candidate' if revision else 'same_observation' if same_date else 'period_comparison',
            'status': status, 'delta_after_minus_before': delta,
            'period_windows_match': before['period_start'] == after['period_start'] and same_date,
            'instrument_identity_matches': all(before.get(k) == after.get(k)
                                               for k in ('ticker', 'action', 'program', 'currency')),
            'resolution': 'none; both observations retained; no automatic supersession',
            'before': left, 'after': right}


def run(args):
    """CLI boundary: verify inputs and constrain selector combinations."""
    if not args.period:
        raise ValueError('--period is required')
    if (args.action or args.program) and not args.ticker:
        raise ValueError('--action/--program require --ticker')
    schema = verify_inputs()
    row = select(args.period, args.accession, args.ticker, args.action, args.program)
    if args.command == 'trace':
        result = trace(row, args.field)
    else:
        if not args.against_period:
            raise ValueError('compare requires --against-period (the before observation)')
        before = select(args.against_period, args.against_accession, args.ticker, args.action, args.program)
        result = compare(before, row, args.field)
    return {'report_version': 1, 'schema_version': schema,
            'input_contract_sha256': hashlib.sha256((Path(edgar.ROOT) / 'data/contract.json').read_bytes()).hexdigest(),
            'scope': 'reviewed frozen snapshot; section locators, not original HTML lines or cell attribution',
            **result}
