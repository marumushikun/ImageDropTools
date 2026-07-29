from __future__ import annotations

import csv
import json
import re
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup

OUT = Path("generated_hyakumeiten")
OUT.mkdir(exist_ok=True)
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36"
})

CATEGORIES = [
    ("bread_tokyo", "パン", "TOKYO", 100),
    ("bread_east", "パン", "EAST", 100),
    ("bread_west", "パン", "WEST", 100),
    ("curry_tokyo", "カレー", "TOKYO", 100),
    ("curry_east", "カレー", "EAST", 100),
    ("curry_west", "カレー", "WEST", 100),
    ("ramen_tokyo", "ラーメン", "TOKYO", 100),
    ("ramen_east", "ラーメン", "EAST", 100),
    ("ramen_west", "ラーメン", "WEST", 100),
    ("sweets_tokyo", "スイーツ", "TOKYO", 100),
    ("sweets_east", "スイーツ", "EAST", 100),
    ("sweets_west", "スイーツ", "WEST", 100),
    ("udon_tokyo", "うどん", "TOKYO", 100),
    ("udon_east", "うどん", "EAST", 100),
    ("udon_west", "うどん", "WEST", 105),
    ("yakiniku_tokyo", "焼肉", "TOKYO", 100),
    ("yakiniku_east", "焼肉", "EAST", 100),
    ("yakiniku_west", "焼肉", "WEST", 100),
    ("yoshoku", "洋食", "全国", 100),
]

REST_RE = re.compile(r"^https?://tabelog\.com/[^/]+/A\d+/A\d+/\d+/?(?:[?#].*)?$", re.I)
TID_RE = re.compile(r"/(\d+)/?$")


def get(url: str) -> requests.Response:
    response = SESSION.get(url, timeout=120, allow_redirects=True)
    response.raise_for_status()
    return response


def prefecture_from_area(area_text: str) -> str:
    area_text = re.sub(r"\s+", " ", area_text).strip()
    if not area_text:
        return ""
    first = area_text.split(" ", 1)[0]
    # The official 2020 page normally writes the full 都道府県 name. Keep a defensive map.
    short = {
        "北海道": "北海道", "東京": "東京都", "大阪": "大阪府", "京都": "京都府",
    }
    if first in short:
        return short[first]
    if first.endswith(("都", "道", "府", "県")):
        return first
    return first + "県"


listings: list[dict] = []
category_reports: list[dict] = []
global_no = 1

for slug, genre, region, expected_count in CATEGORIES:
    source_url = f"https://award.tabelog.com/hyakumeiten/{slug}/2020"
    response = get(source_url)
    final_path = urlparse(response.url).path.rstrip("/")
    assert final_path.endswith(f"/hyakumeiten/{slug}/2020"), (slug, response.url)
    soup = BeautifulSoup(response.content, "lxml")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    assert "2020" in title, (slug, title)

    category_rows: list[dict] = []
    seen_tids: set[str] = set()
    for item in soup.select(".hyakumeiten-shop__item"):
        target = item.select_one("a.hyakumeiten-shop__target[href]")
        name_el = item.select_one(".hyakumeiten-shop__name")
        area_el = item.select_one(".hyakumeiten-shop__area")
        if not target or not name_el:
            continue
        href = urldefrag(urljoin(response.url, target.get("href", "")))[0]
        if not REST_RE.match(href):
            continue
        match = TID_RE.search(urlparse(href).path)
        tabelog_id = match.group(1) if match else ""
        name = name_el.get_text(" ", strip=True)
        area_spans = area_el.find_all("span") if area_el else []
        area_text = area_spans[-1].get_text(" ", strip=True) if area_spans else ""
        prefecture = prefecture_from_area(area_text)
        assert tabelog_id and name and prefecture, (slug, tabelog_id, name, prefecture, area_text)
        assert tabelog_id not in seen_tids, (slug, "duplicate tabelog_id", tabelog_id)
        seen_tids.add(tabelog_id)
        category_rows.append({
            "listing_id": f"HYK2020-{global_no:04d}",
            "category_slug": slug,
            "genre": genre,
            "region": region,
            "category_ordinal": len(category_rows) + 1,
            "listed_name": name,
            "prefecture": prefecture,
            "area_text": area_text,
            "tabelog_url": href,
            "tabelog_id": tabelog_id,
            "source_url": source_url,
            "category_official_count": expected_count,
        })
        global_no += 1

    assert len(category_rows) == expected_count, (slug, len(category_rows), expected_count)
    listings.extend(category_rows)
    category_reports.append({
        "slug": slug,
        "genre": genre,
        "region": region,
        "source_url": source_url,
        "title": title,
        "expected_count": expected_count,
        "actual_count": len(category_rows),
        "first": category_rows[0]["listed_name"],
        "last": category_rows[-1]["listed_name"],
    })

assert len(listings) == 1905, len(listings)
assert len({(x["category_slug"], x["tabelog_id"]) for x in listings}) == 1905

# Unique physical/store pages. One store may appear in several genre/area lists; this table keeps one row per Tabelog ID.
unique: OrderedDict[str, dict] = OrderedDict()
for row in listings:
    tid = row["tabelog_id"]
    if tid not in unique:
        unique[tid] = {
            "tabelog_id": tid,
            "listed_name": row["listed_name"],
            "prefecture": row["prefecture"],
            "area_text": row["area_text"],
            "tabelog_url": row["tabelog_url"],
            "primary_genre": row["genre"],
            "category_slugs": [],
            "category_labels": [],
            "listing_count": 0,
            "first_source_url": row["source_url"],
        }
    u = unique[tid]
    if row["category_slug"] not in u["category_slugs"]:
        u["category_slugs"].append(row["category_slug"])
        u["category_labels"].append(f'{row["genre"]} {row["region"]}')
    u["listing_count"] += 1

unique_rows = []
for u in unique.values():
    unique_rows.append({
        **u,
        "category_slugs": " / ".join(u["category_slugs"]),
        "category_labels": " / ".join(u["category_labels"]),
    })

listing_fields = [
    "listing_id", "category_slug", "genre", "region", "category_ordinal", "listed_name",
    "prefecture", "area_text", "tabelog_url", "tabelog_id", "source_url", "category_official_count",
]
unique_fields = [
    "tabelog_id", "listed_name", "prefecture", "area_text", "tabelog_url", "primary_genre",
    "category_slugs", "category_labels", "listing_count", "first_source_url",
]

for filename, fields, rows in [
    ("hyakumeiten_2020_listings.tsv", listing_fields, listings),
    ("hyakumeiten_2020_unique_stores.tsv", unique_fields, unique_rows),
]:
    with (OUT / filename).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

manifest = {
    "year": 2020,
    "category_count": len(CATEGORIES),
    "genre_count": len({x[1] for x in CATEGORIES}),
    "listing_count": len(listings),
    "unique_store_count": len(unique_rows),
    "multi_listed_store_count": sum(1 for u in unique_rows if u["listing_count"] > 1),
    "max_listing_count_per_store": max(u["listing_count"] for u in unique_rows),
    "category_counts": {x["slug"]: x["actual_count"] for x in category_reports},
    "category_reports": category_reports,
}
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(manifest, ensure_ascii=False, indent=2))
