"""Small reviewable CSV shards; restore and verified raw-source hydration."""
import csv
import hashlib
import zipfile
from pathlib import Path
from . import edgar

ROOT = Path(edgar.ROOT)
FROZEN = ROOT / 'data' / 'frozen'
BUNDLE = ROOT / 'data' / 'sources' / 'sec-sources.zip'
NAMES = ('weekly', 'instrument_weekly', 'filings', 'share_anchors', 'sats_per_share', 'sourced_sats', 'checks')


def snapshot():
    for name in (*NAMES, 'manifest'):
        path = Path(edgar.MANIFEST) if name == 'manifest' else ROOT / 'data' / f'{name}.csv'
        with path.open() as f:
            reader = csv.DictReader(f)
            fields, rows = reader.fieldnames, list(reader)
        dest = FROZEN / name
        dest.mkdir(parents=True, exist_ok=True)
        for old in dest.glob('*.csv'):
            old.unlink()
        # 16 rows keeps every staged file below the repository's 20,000-byte cap.
        for i in range(0, len(rows), 16):
            with (dest / f'{i // 16:03}.csv').open('w') as f:
                writer = csv.DictWriter(f, fields, lineterminator='\n')
                writer.writeheader()
                writer.writerows(rows[i:i+16])


def restore():
    for name in (*NAMES, 'manifest'):
        dest = Path(edgar.MANIFEST) if name == 'manifest' else ROOT / 'data' / f'{name}.csv'
        shards = sorted((FROZEN / name).glob('*.csv'))
        if not shards:
            raise ValueError(f'missing frozen shards: {name}')
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('w') as out:
            for i, p in enumerate(shards):
                lines = p.read_text().splitlines(keepends=True)
                out.writelines(lines if i == 0 else lines[1:])


def hydrate():
    """Fetch missing cached files; verify all against frozen original-byte hashes."""
    with open(edgar.MANIFEST) as f:
        manifest = list(csv.DictReader(f))
    for r in manifest:
        path = Path(edgar.RAW) / r['path']
        if not path.resolve().is_relative_to(Path(edgar.RAW).resolve()):
            raise ValueError('source path outside cache')
        if not path.exists():
            # The frozen index changes upstream. Prefer the archived original bytes.
            if BUNDLE.exists():
                with zipfile.ZipFile(BUNDLE) as archive:
                    try:
                        data = archive.read(r['path'])
                    except KeyError:
                        data = edgar.client().get(r['url'])
            else:
                data = edgar.client().get(r['url'])
            if hashlib.sha256(data).hexdigest() != r['sha256']:
                raise ValueError(f'source changed: {r["url"]}')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        if hashlib.sha256(path.read_bytes()).hexdigest() != r['sha256']:
            raise ValueError(f'cache hash mismatch: {path}')
    return len(manifest)
