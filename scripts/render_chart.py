"""Optional PNG export with Playwright 1.63.0; chart generation itself is stdlib-only."""
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1200, 'height': 850}, device_scale_factor=2)
    page.goto((root / 'figures/card.html').as_uri())
    page.evaluate('document.fonts.ready')
    page.screenshot(path=str(root / 'figures/sunday-tracker@2x.png'))
    page.set_viewport_size({'width': 400, 'height': 300})
    page.screenshot(path=str(root / 'figures/feed400.png'), full_page=True)
    browser.close()
print('figures/sunday-tracker@2x.png (2400x1700); figures/feed400.png')
