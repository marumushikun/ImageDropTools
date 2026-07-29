from __future__ import annotations

import collections
import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

OUT = Path('generated_2021')
OUT.mkdir(exist_ok=True)
HEADERS = {'User-Agent': 'Mozilla/5.0 AppleWebKit/537.36 Chrome/130 Safari/537.36'}
URLS = [
    'https://award.tabelog.com/hyakumeiten/bistro/2021',
    'https://award.tabelog.com/hyakumeiten/ramen_tokyo/2021',
    'https://award.tabelog.com/2021/restaurants/bronze',
]

result = {}
for url in URLS:
    response = requests.get(url, headers=HEADERS, timeout=90)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'lxml')
    ancestor_counts = collections.Counter()
    anchor_rows = []
    for anchor in soup.select('a[href]'):
        href = urljoin(response.url, anchor.get('href', ''))
        if 'tabelog.com/' not in href or not re.search(r'/\d{6,}/?(?:[?#].*)?$', href):
            continue
        lineage = []
        node = anchor
        for depth in range(7):
            if node is None:
                break
            classes = '.'.join(node.get('class', []))
            descriptor = f'{node.name}' + (f'.{classes}' if classes else '')
            lineage.append(descriptor)
            ancestor_counts[descriptor] += 1
            node = node.parent
        anchor_rows.append({
            'text': anchor.get_text(' ', strip=True),
            'href': href,
            'lineage': lineage,
        })
    result[url] = {
        'status': response.status_code,
        'title': soup.title.get_text(' ', strip=True) if soup.title else '',
        'anchor_count': len(anchor_rows),
        'top_ancestor_classes': ancestor_counts.most_common(80),
        'sample_anchors': anchor_rows[:30],
    }

(OUT / 'markup_debug.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({url: data['anchor_count'] for url, data in result.items()}, ensure_ascii=False))
