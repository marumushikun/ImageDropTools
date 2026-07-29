from __future__ import annotations

import json
from pathlib import Path
import requests
from bs4 import BeautifulSoup

HEADERS = {'User-Agent':'Mozilla/5.0 AppleWebKit/537.36 Chrome/130 Safari/537.36'}
OUT = Path('generated_2021')
OUT.mkdir(exist_ok=True)

def inspect(url, selector):
    r = requests.get(url, headers=HEADERS, timeout=90)
    r.raise_for_status()
    soup = BeautifulSoup(r.content, 'lxml')
    card = soup.select_one(selector)
    descendants=[]
    if card:
        for node in card.find_all(True):
            descendants.append({
                'tag': node.name,
                'class': node.get('class', []),
                'text': node.get_text(' ', strip=True)[:300],
                'href': node.get('href',''),
            })
    return {'url':url,'selector':selector,'card_text':card.get_text(' ',strip=True) if card else '', 'descendants':descendants, 'html':str(card)[:20000] if card else ''}

result={
 'hyakumeiten': inspect('https://award.tabelog.com/hyakumeiten/bistro/2021','div.hyakumeiten-shop__item'),
 'award': inspect('https://award.tabelog.com/2021/restaurants/bronze','li.award2021-rstlst__item'),
}
(OUT/'card_debug.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print({k:len(v['descendants']) for k,v in result.items()})
