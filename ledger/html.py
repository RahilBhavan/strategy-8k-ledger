"""Filing HTML -> ordered blocks of paragraphs and tables. stdlib only.

`Blocks`, `num` and `key` are vendored from dat-accretion `dat/parse_mstr.py` with small changes: nested tables are
flattened into the outer cell, cells keep their colspan-free text, and `num` also accepts negative '-x' figures.
"""
import re
from decimal import Decimal
from html.parser import HTMLParser


class Blocks(HTMLParser):
    """Flatten HTML into ('p', text) and ('table', [[cell, ...], ...]); empty and bare '$' / '%' cells dropped."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks, self.buf, self.table, self.row, self.cell = [], [], None, None, None
        self.depth = 0
        self.skip = 0

    def flush(self):
        t = ' '.join(''.join(self.buf).split())
        self.buf = []
        if t:
            self.blocks.append(('p', t))

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'ix:header', 'head'):
            self.skip += 1
        elif tag == 'table':
            self.depth += 1
            if self.depth == 1:
                self.flush()
                self.table = []
        elif self.depth == 1 and tag == 'tr':
            self.row = []
        elif self.depth == 1 and tag in ('td', 'th') and self.row is not None:
            self.cell = []
        elif tag in ('p', 'div', 'br', 'li') and self.table is None:
            self.flush()
        elif tag == 'br' and self.cell is not None:
            self.cell.append(' ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'ix:header', 'head'):
            self.skip = max(0, self.skip - 1)
        elif self.depth == 1 and tag in ('td', 'th') and self.cell is not None:
            c = ' '.join(''.join(self.cell).split())
            self.cell = None
            if c and c not in ('$', '%', '€'):
                self.row.append(c)
        elif self.depth == 1 and tag == 'tr' and self.row is not None:
            if self.row:
                self.table.append(self.row)
            self.row = None
        elif tag == 'table' and self.depth:
            self.depth -= 1
            if self.depth == 0:
                if self.table:
                    self.blocks.append(('table', self.table))
                self.table = None
        elif tag in ('p', 'div', 'li') and self.table is None:
            self.flush()

    def handle_data(self, data):
        if self.skip:
            return
        if self.cell is not None:
            self.cell.append(data)
        elif self.table is None:
            self.buf.append(data)


def blocks(html):
    b = Blocks()
    b.feed(html)
    b.flush()
    return b.blocks


def num(cell):
    """Table cell -> Decimal. '-'/'—' is zero, '(x)' is negative, footnote marks '(1)', '*' and '$' dropped."""
    c = cell.replace('$', '').replace('€', '').replace('*', '').replace('—', '-').replace('–', '-')
    c = re.sub(r'(?<=[\d\-)])\s*(\(\d\)\s*)+$', '', c).replace(',', '').replace(' ', '')
    if c in ('-', ''):
        return Decimal(0)
    if re.fullmatch(r'\(\d+(\.\d+)?\)', c):
        return -Decimal(c[1:-1])
    if not re.fullmatch(r'-?\d+(\.\d+)?', c):
        raise ValueError(f'not a number: {cell!r}')
    return Decimal(c)


def key(label):
    """Header label -> compact key: footnote marks, '*' and whitespace removed, lower case."""
    return re.sub(r'\(\d\)|\*|\s', '', label).lower()
