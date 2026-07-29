from __future__ import annotations

import json
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import build_foodie_2021 as base


def extract(content: bytes, page_url: str) -> dict[str, dict]:
    soup = BeautifulSoup(content, "lxml")
    title = soup.title.get_text(" ", strip=True) if soup.title else page_url
    genre, region = base.parse_list_label(title)
    result: dict[str, dict] = {}
    cards = soup.select("div.hyakumeiten-shop__item")
    for order, card in enumerate(cards, start=1):
        anchor = card.select_one("a.hyakumeiten-shop__target")
        href = urljoin(page_url, anchor.get("href", "")) if anchor else ""
        tid = base.tid_from_url(href)
        name_node = card.select_one(".hyakumeiten-shop__name")
        area_node = card.select_one(".hyakumeiten-shop__area")
        name = name_node.get_text(" ", strip=True) if name_node else ""
        area = area_node.get_text(" ", strip=True) if area_node else ""
        name = re.sub(r"^初選出\s*", "", name).strip()
        pref_token = area.split()[0] if area else ""
        prefecture = base.PREF_FULL.get(pref_token, pref_token)
        station = " ".join(area.split()[1:]) if area else ""
        key = base.store_key(tid, name, prefecture)
        if not name or not prefecture or not key:
            continue
        result[key] = {
            "kind": "百名店",
            "list_title": f"{genre} 百名店",
            "award_class": "百名店",
            "genre": genre,
            "region": region,
            "name": name,
            "prefecture": prefecture,
            "station": station,
            "tabelog_url": href,
            "tabelog_id": tid,
            "store_key": key,
            "source_url": page_url.split("?", 1)[0].rstrip("/"),
            "official_order": order,
            "special": "",
        }
    return result


def archived_snapshots(url: str) -> list[tuple[str, str]]:
    cdx = "https://web.archive.org/cdx/search/cdx"
    params = {
        "url": url.rstrip("/") + "*",
        "output": "json",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "from": "2021",
        "to": "2023",
        "fl": "timestamp,original",
        "collapse": "digest",
        "limit": "40",
    }
    response = requests.get(cdx, params=params, headers=base.HEADERS, timeout=90)
    if response.status_code != 200:
        return []
    try:
        data = response.json()
    except Exception:
        return []
    rows = data[1:] if data and isinstance(data[0], list) else data
    snapshots = []
    for row in rows:
        if len(row) < 2:
            continue
        timestamp, original = row[0], row[1]
        snapshots.append((timestamp, original))
    snapshots.sort(reverse=True)
    return snapshots


def parse_hyakumeiten_with_archive(url: str) -> dict:
    response = base.get(url)
    title = BeautifulSoup(response.content, "lxml").title
    title_text = title.get_text(" ", strip=True) if title else url
    genre, region = base.parse_list_label(title_text)
    merged = extract(response.content, response.url)
    current_count = len(merged)
    used_archives = []

    if current_count < 100:
        for timestamp, original in archived_snapshots(url):
            archive_url = f"https://web.archive.org/web/{timestamp}id_/{original}"
            try:
                archived = requests.get(archive_url, headers=base.HEADERS, timeout=120)
                if archived.status_code != 200:
                    continue
                recovered = extract(archived.content, url)
                before = len(merged)
                for key, record in recovered.items():
                    if key not in merged:
                        merged[key] = record
                if len(merged) > before:
                    used_archives.append({"timestamp": timestamp, "added": len(merged) - before, "archive_url": archive_url})
                if len(merged) >= 100:
                    break
            except Exception:
                continue
            time.sleep(0.1)

    records = list(merged.values())
    # Preserve current-page order; archived-only records follow with deterministic order.
    for order, record in enumerate(records, start=1):
        record["official_order"] = order
        if used_archives and order > current_count:
            record["special"] = "2021年当時の公式アーカイブから復元"
    assert len(records) == 100, f"{url}: current {current_count}, archive union {len(records)}"
    return {
        "url": response.url.split("?", 1)[0].rstrip("/"),
        "title": title_text,
        "genre": genre,
        "region": region,
        "records": records,
        "current_count": current_count,
        "archive_recovery": used_archives,
    }


base.parse_hyakumeiten = parse_hyakumeiten_with_archive
base.main()
