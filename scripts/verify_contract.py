"""Check restored/rebuilt outputs against the reviewed v1 snapshot contract."""
import csv
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
contract = json.loads((root / 'data/contract.json').read_text())
for name, expected in contract['tables'].items():
    path = root / 'data' / ('raw/manifest.csv' if name == 'manifest' else name + '.csv')
    body = path.read_bytes()
    assert hashlib.sha256(body).hexdigest() == expected['sha256'], f'{name}: snapshot bytes differ'
    with path.open(newline='') as f:
        rows = list(csv.reader(f))
    assert rows[0] == expected['columns'], f'{name}: schema differs'
    assert len(rows) - 1 == expected['rows'], f'{name}: row count differs'
archive = contract['source_archive']
assert hashlib.sha256((root / archive['path']).read_bytes()).hexdigest() == archive['sha256']
print(f"schema {contract['schema_version']}: all {len(contract['tables'])} tables/manifest and source archive match reviewed hashes")
