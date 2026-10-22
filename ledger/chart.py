"""Reproducible source-only Sunday tracker SVG/HTML; stdlib, no remote assets."""
import base64
import csv
import datetime as dt
from decimal import Decimal as D
from html import escape
from pathlib import Path
from . import build, edgar

FIG = Path(edgar.ROOT) / 'figures'
H = 1130


def sourced_sats(weeks):
    """Only denominators actually printed for the same date in the weekly filing."""
    return [dict(period_end=w['period_end'], btc_held=w['btc_held'], basic_shares=w['basic_shares'],
                 sats_per_basic_share=str((D(w['btc_held']) * 100000000 / D(w['basic_shares'])).quantize(D('.01'))),
                 doc_url=w['doc_url'], filed=w['filed'])
            for w in weeks if w['basic_shares'] and D(w['basic_shares']) > 0]


COVER_FIELDS = ['share_as_of', 'share_form', 'share_accession', 'share_filed', 'share_url', 'basic_shares',
                'before_period_end', 'btc_held_before', 'before_url', 'after_period_end', 'btc_held_after',
                'after_btc_sold', 'after_url', 'sats_low', 'sats_high']


def cover_sats(weeks, anchors):
    """10-Q/10-K cover-page share counts, bracketed by the weekly holdings either side of the cover date.

    Holdings on the cover date lie between the period ending on or before it and the next period's end only when
    the next period starts the day after and states zero BTC sold; any other cover date is left out."""
    out = []
    for a in anchors:
        before = [w for w in weeks if w['period_end'] <= a['as_of']]
        after = [w for w in weeks if w['period_end'] > a['as_of']]
        if not before or not after:
            continue
        b, n = before[-1], after[0]
        next_day = dt.date.fromisoformat(b['period_end']) + dt.timedelta(days=1)
        if n['period_start'] != next_day.isoformat() or n['btc_sold'] != '0':
            continue
        basic = D(a['basic'])
        out.append(dict(share_as_of=a['as_of'], share_form=a['form'], share_accession=a['accession'],
                        share_filed=a['filed'], share_url=a['doc_url'], basic_shares=a['basic'],
                        before_period_end=b['period_end'], btc_held_before=b['btc_held'], before_url=b['doc_url'],
                        after_period_end=n['period_end'], btc_held_after=n['btc_held'], after_btc_sold=n['btc_sold'],
                        after_url=n['doc_url'],
                        sats_low=str((D(b['btc_held']) * 100000000 / basic).quantize(D('.01'))),
                        sats_high=str((D(n['btc_held']) * 100000000 / basic).quantize(D('.01')))))
    return out


def text(x, y, value, size=20, fill='#52545A', extra=''):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" {extra}>{escape(str(value))}</text>'


def span(start, end):
    a, b = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    return f"{a:%b} {a.day}–{'' if a.month == b.month else f'{b:%b} '}{b.day}"


def write_csv(name, fields, rows):
    with (Path(edgar.ROOT) / 'data' / name).open('w') as f:
        writer = csv.DictWriter(f, fields, lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


def main():
    weeks = build.read('weekly.csv')
    sats = sourced_sats(weeks)
    cover = cover_sats(weeks, build.read('share_anchors.csv'))
    FIG.mkdir(exist_ok=True)
    write_csv('sourced_sats.csv', ['period_end', 'btc_held', 'basic_shares', 'sats_per_basic_share', 'doc_url', 'filed'], sats)
    write_csv('cover_sats.csv', COVER_FIELDS, cover)
    latest = weeks[-1]
    title = f"{int(D(latest['btc_acquired'])):,} BTC purchased in latest period"
    alt = (f"Strategy period purchases and sales from {weeks[0]['period_end']} to {latest['period_end']}. "
           f"Latest purchase {latest['btc_acquired']} BTC; holdings {latest['btc_held']} BTC. "
           f"Sats per basic share use {len(sats)} same-date weekly 8-K share counts from early 2025, then "
           f"{len(cover)} 10-Q/10-K cover-page share counts through {cover[-1]['share_as_of']}, each shown as a range "
           "between the weekly holdings before and after the cover date. No current sats/share value is inferred.")
    fonts = []
    for name, filename in [('Plex', 'IBMPlexSans-Regular.ttf'), ('Anton', 'Anton-Regular.ttf')]:
        p = FIG / 'fonts' / filename
        if p.exists():
            encoded = base64.b64encode(p.read_bytes()).decode()
            fonts.append(f"@font-face{{font-family:{name};src:url(data:font/ttf;base64,{encoded})}}")
    el = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{H}" viewBox="0 0 1200 {H}" role="img">',
          f'<title>{escape(title)}</title><desc>{escape(alt)}</desc>',
          '<style>' + ''.join(fonts) + 'text{font-family:Plex,sans-serif}</style>',
          f'<rect width="1200" height="{H}" fill="#111214"/>',
          text(40, 40, 'Strategy weekly 8-K ledger · Sunday tracker · local draft', 20, '#B7B8B1'),
          text(40, 100, title.upper(), 44, '#F5F5EF', 'style="font-family:Anton,sans-serif"'),
          text(40, 140, f"Period {latest['period_start']} to {latest['period_end']} · {int(latest['btc_held']):,} BTC held", 24, '#F5F5EF'),
          f'<rect x="40" y="170" width="1120" height="{H - 210}" fill="#F5F5EF"/>',
          text(70, 205, 'BTC acquired above zero; BTC sold below zero. Actual filing periods, not calendar resampling.', 20)]
    # Headroom: the top gridline is the next 10,000 above the largest purchase, so no bar overshoots it.
    peak = max(float(w['btc_acquired'] or 0) for w in weeks)
    top = 10000 * (int(peak // 10000) + 1)
    zero, scale = 425, 195 / top
    x0, x1 = 150, 1080
    for amount in range(0, top + 1, 10000):
        y = zero - amount * scale
        el.extend([text(65, round(y+6, 2), f'{amount:,}', 18),
                   f'<line x1="145" x2="1090" y1="{y}" y2="{y}" stroke="#9A9B96" stroke-width="0.5"/>'])
    first_day = dt.date.fromisoformat(weeks[0]['period_end'])
    span_days = (dt.date.fromisoformat(latest['period_end']) - first_day).days
    for i, row in enumerate(weeks):
        x = x0 + (dt.date.fromisoformat(row['period_end']) - first_day).days / span_days * (x1-x0)
        color = '#FFE500' if i == len(weeks)-1 else '#111214'
        for field, sign in [('btc_acquired', 1), ('btc_sold', -1)]:
            if not row[field]:
                continue  # missing is not encoded as a zero observation
            height = float(row[field]) * scale
            if height:
                y = zero-height if sign == 1 else zero
                el.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="5" height="{height:.3f}" fill="{color}" stroke="#111214" stroke-width="0.5"/>')
        if i == len(weeks)-1:
            # A small latest bar can be a pixel tall; a leader and label name it directly.
            el.extend([f'<line x1="{x+2.5:.2f}" x2="{x+2.5:.2f}" y1="{zero-54}" y2="{zero-4}" stroke="#111214" stroke-width="1.5"/>',
                       text(round(x+8, 2), zero-60, f"Latest {span(row['period_start'], row['period_end'])}: "
                            f"{int(D(row['btc_acquired'])):,} BTC", 18, '#111214', 'text-anchor="end"')])
        if i % 16 == 0 or i == len(weeks)-1:
            el.append(text(round(x, 2), 470, row['period_end'][:7], 18, extra='text-anchor="middle"'))
    el.append(text(70, 515, 'Sats per basic share = BTC held × 100,000,000 / basic shares', 22, '#111214'))
    el.append(text(70, 550, 'Weekly 8-K share count, same date as holdings · Jan–Feb 2025 only; later 8-Ks print no share count', 18))
    for x, label in [(70, 'Period end'), (280, 'BTC held'), (490, 'Basic shares (8-K, rounded)'), (900, 'Sats / basic share')]:
        el.append(text(x, 582, label, 18))
    for i, r in enumerate(sats):
        y = 612+i*30
        for x, value in [(70, r['period_end']), (280, f"{int(r['btc_held']):,}"),
                         (490, f"{int(r['basic_shares']):,}"), (900, f"{D(r['sats_per_basic_share']):,.2f}")]:
            el.append(text(x, y, value, 20, '#111214'))
    el.append(text(70, 782, '10-Q/10-K cover share count · holdings from the 8-K periods ending before and after the share date', 18))
    for x, label in [(70, 'Share date'), (210, 'Form'), (280, 'Basic shares (cover)'), (490, 'BTC held before–after'),
                     (800, 'Sats / basic share, low–high')]:
        el.append(text(x, 814, label, 18))
    for i, r in enumerate(cover):
        y = 844+i*30
        held = f"{int(r['btc_held_before']):,}" + ('' if r['btc_held_before'] == r['btc_held_after'] else f"–{int(r['btc_held_after']):,}")
        ratio = f"{D(r['sats_low']):,.2f}" + ('' if r['sats_low'] == r['sats_high'] else f"–{D(r['sats_high']):,.2f}")
        for x, value in [(70, r['share_as_of']), (210, r['share_form']), (280, f"{int(r['basic_shares']):,}"),
                         (490, held), (800, ratio)]:
            el.append(text(x, y, value, 20, '#111214'))
    el.extend([text(70, 1040, 'Source: SEC EDGAR, CIK 1050446 · 8-Ks filed through 2026-10-19 and 10-Q/10-K covers · data/*_sats.csv', 18),
               text(70, 1070, '1 BTC = 100,000,000 sats. Basic shares are not diluted shares. Independent work; no investment recommendation.', 18), '</svg>'])
    svg = ''.join(el)
    (FIG / 'sunday-tracker.svg').write_text(svg)
    (FIG / 'alt.txt').write_text(alt+'\n')
    header = ''.join(el[1:3] + el[4:7])
    panel = ''.join(el[8:-1])
    (FIG / 'card.html').write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Sunday tracker</title>'
        '<style>body{margin:0;background:#111214}.card{position:relative;width:1200px;max-width:100%;'
        f'aspect-ratio:1200/{H};background:#111214}}.head{{position:absolute;left:0;top:0;width:100%;height:{170 / H:.6%}}}'
        f'.panel{{position:absolute;left:3.333333%;top:{170 / H:.6%};width:93.333333%;height:{(H - 210) / H:.6%};background:#F5F5EF}}'
        '.panel svg{display:block;width:100%;height:100%}</style><div class="card" role="img" aria-label="'+escape(alt)+'">'
        '<svg class="head" viewBox="0 0 1200 170">'+header+'</svg><div class="panel">'
        f'<svg viewBox="40 170 1120 {H - 210}">'+panel+'</svg></div></div></html>')
    return 'wrote figures/sunday-tracker.svg, figures/card.html, figures/alt.txt, data/sourced_sats.csv and data/cover_sats.csv'
