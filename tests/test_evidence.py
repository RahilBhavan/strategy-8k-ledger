import csv
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ledger import build, edgar, evidence, freeze, chart


class EvidenceTests(unittest.TestCase):
    def test_latest_week_all_economic_fields_have_source_sections(self):
        row = build.read('weekly.csv')[-1]
        fields = build.WEEK_FIELDS[9:]
        for field in fields:
            if row[field]:
                with self.subTest(field=field):
                    citation = evidence.cite(row, field)
                    self.assertEqual(citation['value'], row[field])
                    self.assertTrue(citation['lines'])
                    self.assertEqual(citation['sha256'], hashlib.sha256(edgar.fetch(row['doc_url'])).hexdigest())

    def test_prose_and_instrument_evidence(self):
        week = build.read('weekly.csv')[1]
        c = evidence.cite(week, 'btc_held')
        self.assertTrue(any('450,000' in r['text'] for r in c['lines']))
        inst = build.read('instrument_weekly.csv')[-1]
        for field in ('shares', 'amount_usd'):
            self.assertTrue(evidence.cite(inst, field)['lines'])

    def test_line_numbers_replay_exactly(self):
        row = build.read('weekly.csv')[-1]
        _, lines = evidence.source_lines(row['doc_url'])
        for r in evidence.cite(row, 'btc_held')['lines']:
            self.assertEqual(r['text'], lines[r['line']-1][1])

    def test_missing_and_unknown_fields_refused(self):
        row = build.read('weekly.csv')[-1]
        for field in ('basic_shares', 'made_up'):
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                evidence.cite(row, field)

    def test_frozen_data_reconstructs_current_csv(self):
        for name in freeze.NAMES:
            rows = []
            for path in sorted((freeze.FROZEN / name).glob('*.csv')):
                with path.open() as f:
                    rows.extend(csv.DictReader(f))
            self.assertEqual(rows, build.read(name+'.csv'), name)

    def test_hydrate_detects_corrupt_cache(self):
        scratch = Path.home() / 'scratch/strategy-8k-ledger'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            raw = Path(temp)
            (raw / 'bad.htm').write_text('tampered')
            manifest = raw / 'manifest.csv'
            with manifest.open('w') as f:
                writer = csv.DictWriter(f, edgar.MANIFEST_FIELDS)
                writer.writeheader(); writer.writerow({'path': 'bad.htm', 'url': 'https://www.sec.gov/example',
                    'sha256': hashlib.sha256(b'original').hexdigest(), 'bytes': 8, 'fetched_utc': '2026-10-21'})
            with patch.object(edgar, 'RAW', str(raw)), patch.object(edgar, 'MANIFEST', str(manifest)):
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    freeze.hydrate()

    def test_hydrate_all_real_hashes_and_retry_idempotence(self):
        self.assertEqual(freeze.hydrate(), 184)
        self.assertEqual(freeze.hydrate(), 184)

    def test_chart_sats_have_only_filed_denominators(self):
        weeks = build.read('weekly.csv')
        sats = chart.sourced_sats(weeks)
        self.assertEqual(len(sats), 5)
        self.assertEqual(sats[-1]['period_end'], '2025-02-23')
        self.assertNotIn('2026-10-18', [r['period_end'] for r in sats])
        self.assertEqual(chart.sourced_sats([weeks[-1]]), [])

    def test_cover_sats_bracket_share_date_with_filed_holdings(self):
        weeks, anchors = build.read('weekly.csv'), build.read('share_anchors.csv')
        rows = chart.cover_sats(weeks, anchors)
        self.assertEqual([r['share_as_of'] for r in rows],
                         ['2025-05-02', '2025-07-31', '2025-10-30', '2026-02-13', '2026-04-26', '2026-07-24'])
        for r in rows:
            with self.subTest(share_as_of=r['share_as_of']):
                self.assertLessEqual(r['before_period_end'], r['share_as_of'])
                self.assertLess(r['share_as_of'], r['after_period_end'])
                self.assertEqual(r['after_btc_sold'], '0')
                self.assertLessEqual(float(r['sats_low']), float(r['sats_high']))
        last = rows[-1]
        self.assertEqual((last['basic_shares'], last['share_accession'], last['btc_held_before'], last['sats_low'],
                          last['sats_high']), ('384225751', '0001050446-26-000044', '843775', '219603.97', '219603.97'))
        self.assertEqual(rows, build.read('cover_sats.csv'))

    def test_cover_sats_refuses_unbounded_holdings(self):
        weeks, anchors = build.read('weekly.csv'), build.read('share_anchors.csv')
        july = next(a for a in anchors if a['as_of'] == '2026-07-24')
        i = next(i for i, w in enumerate(weeks) if w['period_end'] > july['as_of'])
        for change in ({'btc_sold': ''}, {'btc_sold': '5'}, {'period_start': '2026-07-21'}):
            with self.subTest(change=change):
                mutated = weeks[:i] + [{**weeks[i], **change}] + weeks[i+1:]
                self.assertEqual(chart.cover_sats(mutated, [july]), [])
        self.assertEqual(chart.cover_sats(weeks[:i], [july]), [])
        early = next(a for a in anchors if a['as_of'] == '2024-10-21')
        self.assertEqual(chart.cover_sats(weeks, [early]), [])

    def test_no_user_agent_without_contact(self):
        with self.assertRaises(ValueError):
            edgar.SECClient('unnamed')

    def test_sec_retry_then_success_without_synthetic_fallback(self):
        import io
        import urllib.error
        client = edgar.SECClient('Local research contact@example.com')
        error = urllib.error.HTTPError('https://www.sec.gov/test', 429, 'rate limit', {}, None)
        with patch.object(edgar.urllib.request, 'urlopen', side_effect=[error, io.BytesIO(b'filing')]) as request, \
                patch.object(edgar.time, 'sleep') as sleep:
            self.assertEqual(client.get('https://www.sec.gov/test'), b'filing')
            self.assertEqual(request.call_count, 2)
            self.assertIn(unittest.mock.call(5), sleep.call_args_list)
        error.close()

    def test_sec_retry_exhaustion_raises(self):
        import urllib.error
        error = urllib.error.HTTPError('https://www.sec.gov/test', 503, 'unavailable', {}, None)
        with patch.object(edgar.urllib.request, 'urlopen', side_effect=error) as request, \
                patch.object(edgar.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'no synthetic substitute'):
                edgar.SECClient('Local research contact@example.com').get('https://www.sec.gov/test')
            self.assertEqual(request.call_count, 4)
        error.close()
