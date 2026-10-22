"""EDGAR access: submissions index, filing indexes and cached document fetch. stdlib only.

Approach vendored from dat-accretion `dat/edgar.py` (itself from filing-tracker): identifying User-Agent,
throttle, 30 s timeout, 25 MB cap, retry 429/503 with backoff, raise on failure (no synthetic fallback).
Changes here: every fetched document is recorded in data/raw/manifest.csv with URL, UTC fetch time and SHA-256,
so each parsed number can be traced to the exact bytes it came from.
"""
import csv, datetime as dt, hashlib, json, os, time, urllib.error, urllib.request

# Network fetches require the operator to supply an identifying contact User-Agent.
UA = os.environ.get('SEC_USER_AGENT', '')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
MANIFEST = os.path.join(RAW, 'manifest.csv')
MANIFEST_FIELDS = ['path', 'url', 'fetched_utc', 'sha256', 'bytes']
CIK = 1050446


class SECClient:
    RETRY = (429, 503)
    BACKOFF = (5, 15, 45)
    MIN_INTERVAL = 0.15  # about 6-7 requests/s, under SEC's 10/s limit

    def __init__(self, user_agent):
        if not user_agent or '@' not in user_agent:
            raise ValueError('Provide an identifying SEC User-Agent containing a contact email')
        self.user_agent = user_agent
        self.last = 0.0

    def get(self, url):
        for wait in (*self.BACKOFF, None):
            delay = self.MIN_INTERVAL - (time.monotonic() - self.last)
            if delay > 0:
                time.sleep(delay)
            self.last = time.monotonic()
            req = urllib.request.Request(url, headers={'User-Agent': self.user_agent, 'Accept-Encoding': 'identity'})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    body = r.read(25_000_001)
                if len(body) > 25_000_000:
                    raise RuntimeError('SEC response exceeded the 25 MB local limit')
                if body.lstrip()[:200].lower().find(b'undeclared automated tool') >= 0:
                    raise RuntimeError(f'SEC rejected the User-Agent for {url}')
                return body
            except urllib.error.HTTPError as e:
                if e.code not in self.RETRY or wait is None:
                    raise RuntimeError(f'SEC access failed; no synthetic substitute: {url}: {e}') from e
                print(f'EDGAR {e.code} on {url}; retry in {wait}s', flush=True)
                time.sleep(wait)
            except (urllib.error.URLError, TimeoutError) as e:
                raise RuntimeError(f'SEC access failed; no synthetic substitute: {url}: {e}') from e


_client = None


def client():
    global _client
    if _client is None:
        _client = SECClient(UA)
    return _client


def _manifest():
    if not os.path.exists(MANIFEST):
        return {}
    with open(MANIFEST, newline='') as f:
        return {r['path']: r for r in csv.DictReader(f)}


def _record(path, url, body):
    rows = _manifest()
    rel = os.path.relpath(path, RAW)
    rows[rel] = {'path': rel, 'url': url, 'fetched_utc': dt.datetime.now(dt.UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
                 'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)}
    os.makedirs(RAW, exist_ok=True)
    with open(MANIFEST, 'w', newline='') as f:
        w = csv.DictWriter(f, MANIFEST_FIELDS)
        w.writeheader()
        w.writerows(sorted(rows.values(), key=lambda r: r['path']))


def cache_path(url):
    """data/raw/<accession-folder>/<doc> for archive URLs; data/raw/submissions/<file> for the index."""
    parts = url.rstrip('/').split('/')
    if 'submissions' in parts:
        return os.path.join(RAW, 'submissions', parts[-1])
    return os.path.join(RAW, parts[-2], parts[-1])


def fetch(url, refresh=False):
    """Document bytes, cached at cache_path(url). A cache hit makes no request unless refresh=True."""
    path = cache_path(url)
    if refresh or not os.path.exists(path):
        body = client().get(url)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(body)
        _record(path, url, body)
    with open(path, 'rb') as f:
        return f.read()


def fetch_text(url):
    return fetch(url).decode('utf-8', errors='replace')


def fetched_at(url):
    """UTC fetch time recorded for a cached URL, or '' if it predates the manifest."""
    return _manifest().get(os.path.relpath(cache_path(url), RAW), {}).get('fetched_utc', '')


def submissions_url(cik=CIK):
    return f'https://data.sec.gov/submissions/CIK{int(cik):010d}.json'


def filings(cik=CIK, form='8-K', since='2025-01-01', refresh=False):
    """8-K and 8-K/A filings filed on or after `since`, oldest first, from the cached submissions index."""
    recent = json.loads(fetch(submissions_url(cik), refresh=refresh))['filings']['recent']
    out = []
    for i, f in enumerate(recent['form']):
        if f in (form, form + '/A') and recent['filingDate'][i] >= since:
            acc, doc = recent['accessionNumber'][i], recent['primaryDocument'][i]
            folder = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace("-", "")}'
            out.append({'accession': acc, 'form': f, 'filed': recent['filingDate'][i], 'items': recent['items'][i],
                        'folder': folder, 'url': f'{folder}/{doc}'})
    if out and min(r['filed'] for r in out) > since and len(recent['form']) >= 1000:
        oldest = min(recent['filingDate'])
        if oldest > since:
            raise RuntimeError(f'submissions "recent" block starts {oldest}, after {since}; older pages not read')
    return sorted(out, key=lambda r: (r['filed'], r['accession']))


def filing_index(folder):
    """Documents in a filing folder, from EDGAR's index.json: [{'name', 'type'}]."""
    return json.loads(fetch(folder + '/index.json'))['directory']['item']
