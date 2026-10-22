"""Deterministic normalized-line evidence, with original-byte hashes.

Locators identify source sections, not original HTML line numbers or individual cells.
Headers, units and dates remain alongside the value. No external model is involved.
"""
import hashlib
from . import edgar
from .html import blocks
from .parse import norm, is_heading, HEADINGS
import re

DERIVED = {
    'atm_net_proceeds_usd': 'sum of USD ATM amount_usd; zero only when no sales explicitly stated',
    'buyback_usd': 'sum of USD buyback amount_usd',
    'pref_buyback_authorization_increase_usd': 'new authorization minus prior authorization',
    'basic': 'class_a + class_b cover-page counts',
}


def source_lines(url):
    body = edgar.fetch(url)
    expected = edgar._manifest().get(edgar.os.path.relpath(edgar.cache_path(url), edgar.RAW))
    if expected is None or hashlib.sha256(body).hexdigest() != expected['sha256']:
        raise ValueError(f'source hash unavailable or mismatched: {url}; run ledger hydrate')
    lines, section = [], None
    for kind, value in blocks(body.decode('utf-8', errors='replace')):
        if kind == 'p':
            value = norm(value)
            if is_heading(value):
                section = next((n for n, rx in HEADINGS.items() if re.fullmatch(rx, value)), None)
            lines.append((section, value))
        else:
            for row in value:
                lines.append((section, ' | '.join(norm(c) for c in row)))
    return body, lines


def cite(row, field):
    """Return exact source section lines for a populated semantic field."""
    if field not in row or row[field] == '':
        raise ValueError(f'field unavailable: {field}')
    body, lines = source_lines(row['doc_url'])
    if field.startswith('usd_'):
        cats, pattern = {'usd'}, r'USD (?:Reserve|Cash)'
    elif 'buyback' in field or row.get('action') == 'buyback':
        cats, pattern = {'repurchase'}, r'repurchase|buyback'
    elif field.startswith('btc_'):
        cats, pattern = {'btc', 'atm+btc'}, r'bitcoin|BTC'
    elif field in ('class_a', 'class_b', 'basic'):
        cats, pattern = set(), r'As of .*registrant had .*class A common stock'
    elif 'shares' in field and 'ticker' not in row:
        cats, pattern = set(), r'Basic Shares Outstanding|Assumed Diluted|in .000s|\d/\d/2025'
    else:
        cats, pattern = {'atm', 'atm+btc'}, r'ATM|Sales Agreement|Shares|available for issuance'
    selected = [(i + 1, t) for i, (cat, t) in enumerate(lines)
                if cat in cats or re.search(pattern, t, re.I)]
    if not selected:
        raise ValueError(f'no source evidence for {field}; layout unsupported')
    return {'field': field, 'value': row[field], 'period_start': row.get('period_start'),
            'as_of': row.get('period_end', row.get('as_of')), 'filed': row['filed'],
            'accession': row['accession'], 'url': row['doc_url'],
            'sha256': hashlib.sha256(body).hexdigest(),
            'locator_basis': '1-based normalized paragraph/table-row lines, including headers and units',
            'derivation': DERIVED.get(field, 'parser extraction; source section includes context'),
            'lines': [{'line': i, 'text': t} for i, t in selected]}
