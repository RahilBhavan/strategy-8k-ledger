"""Behavior proofs for offline trace and conservative comparison reports."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ledger import build, cli, edgar, evidence, report


class ReportTests(unittest.TestCase):
    def command(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cli.main(list(args)), 0)
        return json.loads(out.getvalue())

    def test_real_period_comparison_retains_both_exact_sources(self):
        result = self.command('compare', '--period', '2026-10-18',
                              '--against-period', '2026-10-11')
        self.assertEqual(result['kind'], 'period_comparison')
        self.assertEqual(result['delta_after_minus_before'], '267')
        self.assertEqual(result['status'], 'changed')
        for side in ('before', 'after'):
            citation = result[side]['evidence'][0]
            _, lines = evidence.source_lines(citation['url'])
            self.assertEqual(len(citation['sha256']), 64)
            for line in citation['lines']:
                self.assertEqual(line['text'], lines[line['line'] - 1][1])

    def test_instrument_trace_and_two_program_ambiguity(self):
        result = self.command('trace', '--period', '2026-10-18', '--ticker', 'MSTR',
                              '--action', 'atm_sale', '--field', 'amount_usd')
        self.assertEqual(result['value'], '22000000')
        self.assertEqual(result['observation']['currency'], 'USD')
        with self.assertRaisesRegex(ValueError, 'found 2'):
            report.select('2025-05-04', ticker='MSTR', action='atm_sale')
        row = report.select('2025-05-04', ticker='MSTR', action='atm_sale', program='2024 Common ATM')
        self.assertEqual(row['program'], '2024 Common ATM')

    def test_reparse_matches_published_week_and_exhibit(self):
        for period in ('2025-01-12', '2026-10-11', '2026-10-18'):
            row = report.select(period)
            with patch.object(edgar, 'client', side_effect=AssertionError('network forbidden')):
                replay = report.select(period, row['accession'])
            self.assertEqual({k: replay[k] for k in build.WEEK_FIELDS}, row)

    def test_synthetic_amendment_conflict_and_duplicate_are_not_superseded(self):
        original = report.select('2026-10-18')
        # Synthetic metadata/value mutation only; never added to the frozen corpus.
        amendment = dict(original, accession='synthetic-amendment', form='8-K/A', btc_held='848518')
        for before, after in ((original, amendment), (amendment, original)):
            result = report.compare(before, after, 'btc_held')
            self.assertEqual(result['kind'], 'revision_candidate')
            self.assertEqual(result['status'], 'conflict')
            self.assertIn('no automatic supersession', result['resolution'])
            self.assertEqual(result['before']['value'], before['btc_held'])
            self.assertEqual(result['after']['value'], after['btc_held'])
        result = report.compare(original, original, 'btc_held')
        self.assertEqual(result['kind'], 'same_observation')
        self.assertEqual(result['status'], 'unchanged')
        self.assertEqual(result['delta_after_minus_before'], '0')

    def test_missing_stays_missing_and_current_ratio_refuses(self):
        before, after = report.select('2025-01-12'), report.select('2026-10-18')
        result = report.compare(before, after, 'basic_shares')
        self.assertEqual(result['status'], 'missing')
        self.assertIsNone(result['delta_after_minus_before'])
        self.assertIsNone(result['after']['value'])
        self.assertEqual(result['after']['evidence'], [])
        for field in ('made_up', 'atm_no_sales_stated'):
            with self.assertRaisesRegex(ValueError, 'unsupported'):
                report.trace(after, field)
        with self.assertRaisesRegex(ValueError, 'same-date.*unavailable'):
            report.compare(before, after, report.RATIO)
        ratio = report.trace(before, report.RATIO)
        self.assertEqual(len(ratio['evidence']), 2)
        self.assertIn('arithmetic precision only', ratio['derivation'])

    def test_nonweekly_real_amendment_refuses(self):
        amendment = next(f for f in build.read('filings.csv') if f['form'] == '8-K/A')
        with self.assertRaisesRegex(ValueError, 'no weekly observations'):
            report.select('2026-10-18', amendment['accession'])

    def test_changed_table_or_manifest_refuses(self):
        scratch = Path.home() / 'scratch/strategy-8k-ledger'
        scratch.mkdir(parents=True, exist_ok=True)
        for name in ('weekly', 'instrument_weekly', 'filings', 'manifest'):
            with self.subTest(name=name), tempfile.TemporaryDirectory(dir=scratch) as temp:
                data = Path(temp)
                for table in ('weekly', 'instrument_weekly', 'filings'):
                    (data / (table + '.csv')).write_bytes((Path(build.DATA) / (table + '.csv')).read_bytes())
                manifest = data / 'manifest.csv'
                manifest.write_bytes(Path(edgar.MANIFEST).read_bytes())
                path = manifest if name == 'manifest' else data / (name + '.csv')
                path.write_bytes(path.read_bytes() + b'\n')
                with patch.object(build, 'DATA', str(data)), patch.object(edgar, 'MANIFEST', str(manifest)):
                    with self.assertRaisesRegex(ValueError, name + ': snapshot bytes differ'):
                        report.verify_inputs()

    def test_cli_invalid_selection_emits_no_partial_json(self):
        for args in [('compare', '--period', '2026-10-18'),
                     ('trace', '--period', '2026-10-18', '--action', 'buyback'),
                     ('trace', '--period', '2026-10-18', '--field', report.RATIO),
                     ('trace', '--period', '2099-01-01')]:
            out = io.StringIO()
            with self.subTest(args=args), contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    cli.main(list(args))
                self.assertEqual(error.exception.code, 2)
                self.assertEqual(out.getvalue(), '')

    def test_repeated_process_restart_is_identical_and_read_only(self):
        paths = [Path(build.DATA) / (name + '.csv') for name in
                 ('weekly', 'instrument_weekly', 'filings')]
        paths.append(Path(edgar.MANIFEST))
        before = [p.read_bytes() for p in paths]
        cmd = [sys.executable, '-m', 'ledger', 'compare', '--period', '2026-10-18',
               '--against-period', '2026-10-11', '--ticker', 'MSTR',
               '--action', 'atm_sale', '--field', 'amount_usd']
        first = subprocess.check_output(cmd, cwd=edgar.ROOT)
        self.assertEqual(first, subprocess.check_output(cmd, cwd=edgar.ROOT))
        self.assertEqual(before, [p.read_bytes() for p in paths])
