"""Reproducible source-only Sunday tracker SVG/HTML; stdlib, no remote assets."""
import base64
import csv
import datetime as dt
from decimal import Decimal as D
from html import escape
from pathlib import Path
from . import build, edgar

FIG = Path(edgar.ROOT) / 'figures'


def sourced_sats(weeks):
    """Only denominators actually printed for the same date in the weekly filing."""
    return [dict(period_end=w['period_end'], btc_held=w['btc_held'], basic_shares=w['basic_shares'],
                 sats_per_basic_share=str((D(w['btc_held']) * 100000000 / D(w['basic_shares'])).quantize(D('.01'))),
                 doc_url=w['doc_url'], filed=w['filed'])
            for w in weeks if w['basic_shares'] and D(w['basic_shares']) > 0]


def text(x, y, value, size=20, fill='#52545A', extra=''):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" {extra}>{escape(str(value))}</text>'


def main():
    weeks = build.read('weekly.csv')
    sats = sourced_sats(weeks)
    FIG.mkdir(exist_ok=True)
    with (Path(edgar.ROOT) / 'data' / 'sourced_sats.csv').open('w') as f:
        writer = csv.DictWriter(f, ['period_end', 'btc_held', 'basic_shares', 'sats_per_basic_share', 'doc_url', 'filed'], lineterminator='\n')
        writer.writeheader(); writer.writerows(sats)
    latest = weeks[-1]
    title = f"{int(D(latest['btc_acquired'])):,} BTC purchased in latest period"
    alt = (f"Strategy period purchases and sales from {weeks[0]['period_end']} to {latest['period_end']}. "
           f"Latest purchase {latest['btc_acquired']} BTC; holdings {latest['btc_held']} BTC. "
           f"Sats per basic share are shown only for {len(sats)} same-date filed denominators in early 2025. "
           "No current sats/share value is inferred.")
    fonts = []
    for name, filename in [('Plex', 'IBMPlexSans-Regular.ttf'), ('Anton', 'Anton-Regular.ttf')]:
        p = FIG / 'fonts' / filename
        # Shared installed design-system assets are a fallback when raw font copies are absent.
        if not p.exists():
            p = Path.home() / '.codex/skills/rahil-design/assets/fonts' / filename
        if p.exists():
            encoded = base64.b64encode(p.read_bytes()).decode()
            fonts.append(f"@font-face{{font-family:{name};src:url(data:font/ttf;base64,{encoded})}}")
    el = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="850" viewBox="0 0 1200 850" role="img">',
          f'<title>{escape(title)}</title><desc>{escape(alt)}</desc>',
          '<style>' + ''.join(fonts) + 'text{font-family:Plex,sans-serif}</style>',
          '<rect width="1200" height="850" fill="#111214"/>',
          text(40, 40, 'Strategy weekly 8-K ledger · Sunday tracker · local draft', 20, '#B7B8B1'),
          text(40, 100, title.upper(), 44, '#F5F5EF', 'style="font-family:Anton,sans-serif"'),
          text(40, 140, f"Period {latest['period_start']} to {latest['period_end']} · {int(latest['btc_held']):,} BTC held", 24, '#F5F5EF'),
          '<rect x="40" y="170" width="1120" height="640" fill="#F5F5EF"/>',
          text(70, 205, 'BTC acquired above zero; BTC sold below zero. Actual filing periods, not calendar resampling.', 20)]
    zero, scale = 425, 210 / max(float(w['btc_acquired'] or 0) for w in weeks)
    x0, x1 = 150, 1080
    for amount in (0, 10000, 20000):
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
        if i % 16 == 0 or i == len(weeks)-1:
            el.append(text(round(x, 2), 470, row['period_end'][:7], 18, extra='text-anchor="middle"'))
    el.append(text(70, 510, 'Sats per basic share · only same-date denominators printed in weekly filings', 22, '#111214'))
    for x, label in [(70, 'Period end'), (280, 'BTC held'), (490, 'Basic shares (filed, rounded)'), (900, 'Sats / basic share')]:
        el.append(text(x, 545, label, 20))
    for i, r in enumerate(sats):
        y = 580+i*30
        for x, value in [(70, r['period_end']), (280, f"{int(r['btc_held']):,}"),
                         (490, f"{int(r['basic_shares']):,}"), (900, f"{D(r['sats_per_basic_share']):,.2f}")]:
            el.append(text(x, y, value, 20, '#111214'))
    el.extend([text(70, 755, 'Source: SEC EDGAR, CIK 1050446 · weekly 8-Ks filed through 2026-10-19. See data/weekly.csv URLs.', 18),
               text(70, 785, '1 BTC = 100,000,000 sats. Basic shares are not diluted shares. Independent work; no investment recommendation.', 18), '</svg>'])
    svg = ''.join(el)
    (FIG / 'sunday-tracker.svg').write_text(svg)
    (FIG / 'alt.txt').write_text(alt+'\n')
    header = ''.join(el[1:3] + el[4:7])
    panel = ''.join(el[8:-1])
    (FIG / 'card.html').write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Sunday tracker</title>'
        '<style>body{margin:0;background:#111214}.card{position:relative;width:1200px;max-width:100%;'
        'aspect-ratio:1200/850;background:#111214}.head{position:absolute;left:0;top:0;width:100%;height:20%}'
        '.panel{position:absolute;left:3.333333%;top:20%;width:93.333333%;height:75.294118%;background:#F5F5EF}'
        '.panel svg{display:block;width:100%;height:100%}</style><div class="card" role="img" aria-label="'+escape(alt)+'">'
        '<svg class="head" viewBox="0 0 1200 170">'+header+'</svg><div class="panel">'
        '<svg viewBox="40 170 1120 640">'+panel+'</svg></div></div></html>')
    return 'wrote figures/sunday-tracker.svg, figures/card.html, figures/alt.txt and data/sourced_sats.csv'
