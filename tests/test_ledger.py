"""Tests against the real cached filings in data/raw. No network: any fetch that misses the cache fails."""
import csv, hashlib, os, re, unittest
from decimal import Decimal as D

from ledger import build, checks, diff, edgar, shares
from ledger.parse import NotWeekly, UnknownLayout, cell_amount, parse_document


class NoNetwork:
    def get(self, url):
        raise AssertionError(f'test tried to fetch {url}; the cache in data/raw should hold it')


edgar._client = NoNetwork()
FILINGS = {f['accession']: f for f in edgar.filings()}


def slurp(path, mode='r'):
    with open(path, mode) as f:
        return f.read()


def parsed(acc):
    return build.parse_filing(FILINGS[acc])


def html_of(acc):
    return edgar.fetch_text(FILINGS[acc]['url'])


class ProseEra(unittest.TestCase):
    def test_jan_13_2025_prose_week(self):
        _, role, p = parsed('0001193125-25-005000')
        self.assertEqual(role, '8-K body')
        [w] = p.weeks
        self.assertEqual((w.period_start, w.period_end, w.layout), ('2025-01-06', '2025-01-12', 'prose'))
        self.assertEqual((w.btc_acquired, w.btc_held, w.btc_avg_purchase_price), (2530, 450000, 95972))
        self.assertEqual(w.btc_purchase_usd, D('243e6'))
        self.assertEqual(w.btc_cost_basis_usd, D('28.2e9'))
        [i] = p.instruments
        self.assertEqual((i.ticker, i.shares, i.amount_usd, i.available_usd), ('MSTR', 710425, D('243e6'), D('6.53e9')))
        # the company's KPI table printed share counts that week (in thousands)
        self.assertEqual((w.basic_shares, w.assumed_diluted_shares), (D('246489000'), D('282418000')))

    def test_jan_6_2025_purchases_to_dec_31_belong_to_the_jan_5_holdings_week(self):
        _, _, p = parsed('0001193125-25-001854')
        [w] = p.weeks
        self.assertEqual((w.period_start, w.period_end, w.btc_acquired, w.btc_held), ('2024-12-30', '2025-01-05', 1070, 447470))
        [i] = p.instruments
        self.assertEqual((i.period_end, i.shares, i.available_usd), ('2025-01-05', 319586, D('6.77e9')))

    def test_no_trade_week_states_zero(self):
        _, _, p = parsed('0001193125-25-018889')
        [w] = p.weeks
        self.assertEqual((w.btc_acquired, w.btc_held), (0, 471107))


class TableEra(unittest.TestCase):
    def test_march_2025_summary_cells_carry_units(self):
        _, _, p = parsed('0000950170-25-047219')
        got = {i.ticker: (i.shares, i.amount_usd, i.available_usd) for i in p.instruments}
        self.assertEqual(got['MSTR'], (3645528, D('1.20e9'), D('2.37e9')))
        self.assertEqual(got['STRK'], (213807, D('18.52e6'), D('20.97e9')))
        [w] = p.weeks
        self.assertEqual((w.btc_acquired, w.btc_purchase_usd, w.btc_held, w.btc_avg_cost_basis),
                         (22048, D('1.92e9'), 528185, 67458))

    def test_two_common_atm_programs_in_one_week(self):
        _, _, p = parsed('0000950170-25-063168')
        progs = {i.program: i for i in p.instruments if i.ticker == 'MSTR'}
        self.assertEqual(set(progs), {'2024 Common ATM', '2025 Common ATM'})
        self.assertEqual(progs['2025 Common ATM'].available_usd, D('21e9'))
        self.assertEqual(progs['2024 Common ATM'].shares, 353825)

    def test_oct_5_2026_has_two_sub_periods(self):
        _, _, p = parsed('0001193125-26-413164')
        self.assertEqual([(w.period_start, w.period_end, w.btc_held) for w in p.weeks],
                         [('2026-09-28', '2026-09-30', 847666), ('2026-10-01', '2026-10-04', 848000)])
        bb = {(i.period_end, i.ticker): i.shares for i in p.instruments if i.action == 'buyback' and i.shares}
        self.assertEqual(bb, {('2026-09-30', 'STRC'): 1033168, ('2026-10-04', 'STRC'): 740634})
        last = p.weeks[-1]
        self.assertEqual((last.usd_reserve, last.usd_cash), (D('4.88e9'), D('833.4e6')))
        self.assertEqual((p.weeks[0].pref_buyback_remaining_usd, last.pref_buyback_remaining_usd),
                         (D('620.9e6'), D('547.2e6')))

    def test_oct_13_2026_tables_moved_to_exhibit_99_1(self):
        url, role, p = parsed('0001193125-26-419726')
        self.assertEqual(role, 'EX-99.1')
        self.assertTrue(url.endswith('mstr-ex99_1.htm'))
        [w] = p.weeks
        self.assertEqual((w.btc_held, w.btc_avg_cost_basis, w.usd_reserve, w.usd_cash, w.pref_buyback_remaining_usd),
                         (848250, 75444, D('4.88e9'), D('640.5e6'), D('354.8e6')))
        cap = {i.ticker: i.available_usd for i in p.instruments if i.action == 'atm_sale'}
        self.assertEqual(cap, {'MSTR': D('18807.6e6'), 'STRF': D('1619.3e6'), 'STRC': D('17510.8e6'),
                               'STRK': D('2100.0e6'), 'STRD': D('4014.8e6')})

    def test_sale_weeks_record_btc_sold(self):
        _, _, p = parsed('0001193125-26-295586')
        self.assertEqual([(w.btc_sold, w.btc_held) for w in p.weeks], [(1363, 846000), (2225, 843775)])

    def test_mstr_notional_is_blank_not_zero(self):
        _, _, p = parsed('0001193125-26-424688')
        mstr = next(i for i in p.instruments if i.ticker == 'MSTR' and i.action == 'atm_sale')
        self.assertIsNone(mstr.notional_usd)
        self.assertEqual((mstr.shares, mstr.amount_usd), (140872, D('22.0e6')))

    def test_earnings_8k_is_not_weekly(self):
        with self.assertRaises(NotWeekly):
            parsed('0001628280-26-051027')


class FailLoudly(unittest.TestCase):
    """Altered copies of real filings: an unrecognised layout must raise, not be guessed at."""

    def test_renamed_atm_column(self):
        html = html_of('0001193125-26-424688').replace('Net Proceeds', 'Gross Receipts', 1)
        with self.assertRaisesRegex(UnknownLayout, 'unknown row|no recognised header'):
            parse_document(html, 'altered')

    def test_unknown_security_row(self):
        html = html_of('0001193125-26-424688').replace('STRD Stock', 'STRX Shares', 1)
        with self.assertRaisesRegex(UnknownLayout, 'unknown row'):
            parse_document(html, 'altered')

    def test_renamed_btc_column(self):
        html = html_of('0001193125-26-424688').replace('Average Purchase Price', 'Mean Unit Cost', 1)
        with self.assertRaisesRegex(UnknownLayout, 'unknown BTC column'):
            parse_document(html, 'altered')

    def test_renamed_section_heading_with_trade_table(self):
        html = html_of('0001193125-26-424688').replace('BTC Update', 'Digital Asset Activity', 1)
        with self.assertRaisesRegex(UnknownLayout, 'outside a recognised weekly section'):
            parse_document(html, 'altered')

    def test_reworded_prose_purchase(self):
        html = html_of('0001193125-25-005000').replace('at an average price of approximately',
                                                       'averaging roughly', 1)
        with self.assertRaisesRegex(UnknownLayout, 'bitcoin-purchase sentence'):
            parse_document(html, 'altered')

    def test_amount_cells(self):
        self.assertEqual(cell_amount('$ 22.0 (3)', D(10) ** 6, 'x')[0], D('22.0e6'))
        self.assertEqual(cell_amount('1.92 billion', None, 'x'), (D('1.92e9'), D('5e6') * 2))
        self.assertEqual(cell_amount('$2.37 billion of MSTR Shares', None, 'x')[0], D('2.37e9'))
        self.assertEqual(cell_amount('-', None, 'x')[0], 0)
        with self.assertRaises(UnknownLayout):
            cell_amount('1,619.3', None, 'x')  # no unit in cell or header


class Outputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.weeks = build.read('weekly.csv')
        cls.insts = build.read('instrument_weekly.csv')

    def test_rebuild_is_identical(self):
        before = {n: slurp(os.path.join(build.DATA, n)) for n in ('weekly.csv', 'instrument_weekly.csv')}
        build.build()
        for n, text in before.items():
            self.assertEqual(slurp(os.path.join(build.DATA, n)), text, n)

    def test_range_and_unique_weeks(self):
        ends = [w['period_end'] for w in self.weeks]
        self.assertEqual(len(ends), len(set(ends)))
        self.assertEqual((ends[0], ends[-1]), ('2025-01-05', '2026-10-18'))
        self.assertEqual(len(self.weeks), 97)

    def test_every_row_carries_provenance_and_cached_bytes_match(self):
        manifest = {r['url']: r for r in csv.DictReader(slurp(edgar.MANIFEST).splitlines())}
        for r in self.weeks + self.insts:
            self.assertRegex(r['doc_url'], r'^https://www\.sec\.gov/Archives/edgar/data/1050446/\d{18}/')
            self.assertRegex(r['accession'], r'^\d{10}-\d{2}-\d{6}$')
            self.assertLessEqual(r['period_start'], r['period_end'])
            self.assertLessEqual(r['period_end'], r['filed'])
        for url in {r['doc_url'] for r in self.weeks}:
            body = slurp(edgar.cache_path(url), 'rb')
            self.assertEqual(hashlib.sha256(body).hexdigest(), manifest[url]['sha256'], url)

    def test_instrument_tickers_and_stre_absent(self):
        self.assertEqual({r['ticker'] for r in self.insts}, {'MSTR', 'STRK', 'STRF', 'STRD', 'STRC'})


class Checks(unittest.TestCase):
    def test_no_unexplained_breaks(self):
        res = checks.run()
        self.assertEqual([r for r in res if r['status'] == 'BREAK'], [])
        rolls = [r for r in res if r['check'] == 'roll']
        self.assertEqual(len(rolls), 96)
        for r in rolls:
            self.assertLessEqual(abs(r['diff']), 1)  # every exception is a 1 BTC rounding residual
        self.assertEqual(sum(r['status'] == 'KNOWN_EXCEPTION' for r in rolls), 9)

    def test_roll_flags_an_injected_missing_purchase(self):
        weeks = build.read('weekly.csv')
        w = next(x for x in weeks if x['period_end'] == '2026-10-18')
        w['btc_acquired'] = '0'
        res = checks.run(weeks, build.read('instrument_weekly.csv'))
        bad = [r for r in res if r['status'] == 'BREAK' and r['check'] == 'roll']
        self.assertEqual([(r['period_end'], r['diff']) for r in bad], [('2026-10-18', 267)])
        checks.run()  # restore data/checks.csv

    def test_stated_avg_cost_recomputes(self):
        w = build.read('weekly.csv')[-1]
        self.assertAlmostEqual(float(D(w['btc_cost_basis_usd']) / D(w['btc_held'])), 75446, delta=6)


class SharesAndDiff(unittest.TestCase):
    def test_cover_page_anchor(self):
        a = {r['as_of']: r for r in shares.anchors()}
        self.assertEqual(a['2026-07-24']['basic'], D(364585501 + 19640250))

    def test_roll_forward_misses_are_small(self):
        _, est, res = shares.run()
        self.assertEqual(len(res), 6)
        for r in res:
            self.assertLess(abs(r['miss_pct']), 2, r)
        self.assertEqual(est[-1]['period_end'], '2026-10-18')

    def test_diff_latest(self):
        out = diff.diff()
        self.assertIn('848,250 -> 848,517 BTC (+267)', out)
        self.assertIn('roll check    848,250 + 267 - 0 = 848,517; stated 848,517 OK', out)
        self.assertIn('STRC  1,938,780 shares for $193.1M', out)
        self.assertRegex(out, re.escape('USD Reserve   $4.88B -> $4.83B'))


if __name__ == '__main__':
    unittest.main()
