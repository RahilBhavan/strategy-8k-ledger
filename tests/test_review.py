"""Regression proofs from the publication correctness review."""
import unittest
from unittest.mock import patch
from ledger import build, checks


class ReconciliationReview(unittest.TestCase):
    def test_known_exception_does_not_hide_different_corruption(self):
        weeks = build.read('weekly.csv')
        row = next(w for w in weeks if w['period_end'] == '2025-10-12')
        row['btc_held'] = '1'
        with patch.object(build, 'write'):
            result = checks.run(weeks)
        roll = next(r for r in result if r['period_end'] == row['period_end'] and r['check'] == 'roll')
        self.assertEqual(roll['status'], 'BREAK')


class CacheReview(unittest.TestCase):
    def test_fetch_rejects_tampered_bytes_before_parsing(self):
        import csv
        import hashlib
        import tempfile
        from pathlib import Path
        from ledger import edgar
        scratch = Path.home() / 'scratch/strategy-8k-ledger'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            raw = Path(temp)
            (raw / 'doc').mkdir()
            (raw / 'doc/source.htm').write_bytes(b'tampered')
            manifest = raw / 'manifest.csv'
            with manifest.open('w') as f:
                writer = csv.DictWriter(f, edgar.MANIFEST_FIELDS)
                writer.writeheader()
                writer.writerow(dict(path='doc/source.htm', url='https://www.sec.gov/doc/source.htm',
                    sha256=hashlib.sha256(b'original').hexdigest(), bytes=8, fetched_utc='2026-10-21'))
            with patch.object(edgar, 'RAW', str(raw)), patch.object(edgar, 'MANIFEST', str(manifest)):
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    edgar.fetch('https://www.sec.gov/doc/source.htm')


class CitationReview(unittest.TestCase):
    def test_share_count_citation_includes_denominator_dates(self):
        from ledger import evidence
        for w in build.read('weekly.csv'):
            if not w['basic_shares']:
                continue
            with self.subTest(period=w['period_end']):
                cited = evidence.cite(w, 'basic_shares')
                year, month, day = w['period_end'].split('-')
                date = f'{int(month)}/{int(day)}/{year}'
                self.assertTrue(any(date in r['text'] for r in cited['lines']))


class FrozenSourceReview(unittest.TestCase):
    def test_empty_cache_hydration_and_restart_replay_offline(self):
        import tempfile
        from pathlib import Path
        from ledger import edgar, freeze
        scratch = Path.home() / 'scratch/strategy-8k-ledger'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            raw = Path(temp)
            manifest = raw / 'manifest.csv'
            manifest.write_bytes(Path(edgar.MANIFEST).read_bytes())
            with patch.object(edgar, 'RAW', str(raw)), patch.object(edgar, 'MANIFEST', str(manifest)), \
                    patch.object(edgar, 'client', side_effect=AssertionError('network forbidden')):
                self.assertEqual(freeze.hydrate(), 184)
                before = {p.relative_to(raw): p.read_bytes() for p in raw.rglob('*') if p.is_file()}
                self.assertEqual(freeze.hydrate(), 184)
                self.assertEqual(before, {p.relative_to(raw): p.read_bytes() for p in raw.rglob('*') if p.is_file()})


class ParserReview(unittest.TestCase):
    def test_renamed_trade_trigger_headers_refuse_partial_output(self):
        from ledger import edgar
        from ledger.parse import parse_document, UnknownLayout
        filing = next(f for f in edgar.filings() if f['accession'] == '0001193125-26-424688')
        html = edgar.fetch_text(filing['url'])
        for old, new in [('Shares Sold', 'Shares Issued'), ('Shares Repurchased', 'Shares Bought')]:
            with self.subTest(header=old), self.assertRaises(UnknownLayout):
                parse_document(html.replace(old, new), 'changed header')


class AmendmentReview(unittest.TestCase):
    def test_duplicate_or_amended_period_refuses_before_writing(self):
        from ledger import edgar
        from ledger.parse import UnknownLayout
        f = next(f for f in edgar.filings() if f['accession'] == '0001193125-26-424688')
        parsed = build.parse_filing(f)
        for candidate in [f, dict(f, accession='0001193125-26-999999', form='8-K/A', filed='2026-10-20')]:
            with self.subTest(form=candidate['form']), \
                    patch.object(edgar, 'filings', return_value=[f, candidate]), \
                    patch.object(build, 'parse_filing', return_value=parsed), \
                    patch.object(build, 'write') as write:
                with self.assertRaisesRegex(UnknownLayout, 'duplicate economic period'):
                    build.build()
                write.assert_not_called()


class ConflictingTableReview(unittest.TestCase):
    def test_conflicting_holdings_tables_refuse_in_either_order(self):
        from ledger.parse import parse_document, UnknownLayout
        def table(n):
            return ('<table><tr><td>As of October 18, 2026</td></tr>'
                    '<tr><td>Aggregate BTC Holdings</td></tr>'
                    f'<tr><td>{n}</td></tr></table>')
        for values in [(100, 200), (200, 100)]:
            with self.subTest(values=values), self.assertRaisesRegex(UnknownLayout, 'conflicting'):
                parse_document('<p>BTC Update</p>' + ''.join(map(table, values)), 'conflict')


class OfflineCitationReview(unittest.TestCase):
    def test_missing_source_refuses_without_attempting_network(self):
        import tempfile
        from pathlib import Path
        from ledger import edgar, evidence
        scratch = Path.home() / 'scratch/strategy-8k-ledger'
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            with patch.object(edgar, 'RAW', temp), \
                    patch.object(edgar, 'client', side_effect=AssertionError('network forbidden')):
                with self.assertRaisesRegex(ValueError, 'source cache unavailable'):
                    evidence.cite(build.read('weekly.csv')[-1], 'btc_held')
