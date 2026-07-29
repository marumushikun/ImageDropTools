from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://award.tabelog.com"
YEAR = "2021"
OUT = Path("generated_2021")
OUT.mkdir(exist_ok=True)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
}

# Broad historical/current slug vocabulary. Successful pages also contribute links,
# so this is only the seed and not the final source of truth.
SEED_SLUGS = {
    "soba", "japanese", "japanese_east", "japanese_west", "gyoza", "izakaya",
    "bistro", "cafe", "yakitori", "tonkatsu", "teishoku", "unagi", "bread",
    "bread_tokyo", "bread_east", "bread_west", "curry", "curry_tokyo", "curry_east",
    "curry_west", "ramen", "ramen_tokyo", "ramen_east", "ramen_west", "sweets",
    "sweets_tokyo", "sweets_east", "sweets_west", "udon", "udon_east", "udon_west",
    "udon_kagawa", "yakiniku", "yakiniku_tokyo", "yakiniku_east", "yakiniku_west",
    "yoshoku", "chinese", "chinese_tokyo", "chinese_east", "chinese_west",
    "hamburger", "okonomiyaki", "bar", "kissaten", "asia_ethnic", "asian_ethnic",
    "spanish", "spain", "ice", "gelato", "ice_gelato", "wagashi", "kanmi",
    "wagashi_kanmi", "standing_bar", "tachinomi", "chicken", "toriryori",
    "french", "italian", "sushi", "tempura", "eel", "coffee", "pizza",
}

session = requests.Session()
session.headers.update(HEADERS)


def get(url: str, *, timeout: int = 60) -> requests.Response:
    response = session.get(url, timeout=timeout, allow_redirects=True)
    return response


def restaurant_id(url: str) -> str:
    match = re.search(r"/(\d{6,})/?(?:[?#].*)?$", url)
    return match.group(1) if match else ""


def page_links(soup: BeautifulSoup, base_url: str) -> set[str]:
    links: set[str] = set()
    for anchor in soup.select("a[href]"):
        href = urljoin(base_url, anchor.get("href", ""))
        if href.startswith(BASE + "/hyakumeiten/"):
            links.add(href.split("#", 1)[0].split("?", 1)[0].rstrip("/"))
    return links


def title_text(soup: BeautifulSoup) -> str:
    h1 = soup.select_one("h1")
    if h1:
        text = h1.get_text(" ", strip=True)
        if text:
            return text
    if soup.title:
        return soup.title.get_text(" ", strip=True)
    return ""


def parse_restaurants(soup: BeautifulSoup, page_url: str) -> list[dict]:
    # The historical pages have changed markup over time. Extract unique Tabelog
    # restaurant links first, then recover labels from the closest meaningful card.
    found: dict[str, dict] = {}
    for anchor in soup.select("a[href]"):
        href = urljoin(page_url, anchor.get("href", ""))
        if "tabelog.com/" not in href:
            continue
        tid = restaurant_id(href)
        if not tid:
            continue

        name = anchor.get_text(" ", strip=True)
        container = anchor
        for _ in range(6):
            parent = container.parent
            if parent is None:
                break
            container = parent
            class_text = " ".join(container.get("class", []))
            if any(token in class_text.lower() for token in ("item", "card", "list", "rst")):
                break
        blob = container.get_text(" ", strip=True) if container else name

        if not name or len(name) > 120 or name.lower() in {"食べログ", "詳細", "公式ページ"}:
            selectors = [
                ".hyakumeiten-rst-list__rst-name", ".rst-name", ".restaurant-name",
                "h2", "h3", "h4", "strong",
            ]
            recovered = ""
            for selector in selectors:
                node = container.select_one(selector) if container else None
                if node:
                    recovered = node.get_text(" ", strip=True)
                    if recovered:
                        break
            name = recovered or name

        # Prefer the shortest plausible non-navigation label among anchors in the card.
        if container:
            candidates = []
            for node in container.select("a, h2, h3, h4, strong"):
                text = node.get_text(" ", strip=True)
                if 1 < len(text) <= 80 and text not in {"食べログ", "詳細", "公式ページ", "口コミ"}:
                    candidates.append(text)
            if candidates:
                candidates.sort(key=lambda x: ("駅" in x or "県" in x, len(x)))
                if not name or len(candidates[0]) < len(name):
                    name = candidates[0]

        record = {
            "tabelog_id": tid,
            "tabelog_url": href,
            "name": name,
            "text": blob[:500],
        }
        if tid not in found or (not found[tid]["name"] and name):
            found[tid] = record
    return list(found.values())


def discover_sitemap_urls() -> set[str]:
    urls: set[str] = set()
    queue = [
        BASE + "/sitemap.xml",
        BASE + "/sitemap_index.xml",
        BASE + "/hyakumeiten/sitemap.xml",
    ]
    visited: set[str] = set()
    while queue:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        try:
            response = get(url)
        except Exception:
            continue
        if response.status_code != 200 or not response.content:
            continue
        soup = BeautifulSoup(response.content, "xml")
        locs = [node.get_text(strip=True) for node in soup.select("loc")]
        for loc in locs:
            if loc.endswith(".xml") and len(queue) < 100:
                queue.append(loc)
            if f"/hyakumeiten/" in loc and f"/{YEAR}" in loc:
                urls.add(loc.split("#", 1)[0].split("?", 1)[0].rstrip("/"))
    return urls


def main() -> None:
    candidates: set[str] = {f"{BASE}/hyakumeiten/{slug}/{YEAR}" for slug in SEED_SLUGS}

    for root_url in (BASE + "/hyakumeiten", BASE + "/hyakumeiten/"):
        try:
            response = get(root_url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "lxml")
                for link in page_links(soup, response.url):
                    parts = urlparse(link).path.strip("/").split("/")
                    if len(parts) >= 2:
                        candidates.add(f"{BASE}/hyakumeiten/{parts[1]}/{YEAR}")
        except Exception:
            pass

    candidates |= discover_sitemap_urls()

    successful: dict[str, dict] = {}
    checked: list[dict] = []
    queue = sorted(candidates)
    seen: set[str] = set()

    while queue:
        url = queue.pop(0).rstrip("/")
        if url in seen:
            continue
        seen.add(url)
        try:
            response = get(url)
            soup = BeautifulSoup(response.content, "lxml")
            title = title_text(soup)
            restaurants = parse_restaurants(soup, response.url)
            valid = response.status_code == 200 and YEAR in response.url and len(restaurants) >= 20
            checked.append({
                "url": url,
                "status": response.status_code,
                "final_url": response.url,
                "title": title,
                "restaurant_count": len(restaurants),
                "valid": valid,
            })
            if valid:
                canonical = response.url.split("#", 1)[0].split("?", 1)[0].rstrip("/")
                successful[canonical] = {
                    "url": canonical,
                    "title": title,
                    "restaurant_count": len(restaurants),
                    "restaurants": restaurants,
                }
                for link in page_links(soup, response.url):
                    path = urlparse(link).path.strip("/").split("/")
                    if len(path) >= 3 and path[-1] == YEAR:
                        new_url = f"{BASE}/" + "/".join(path)
                        if new_url not in seen:
                            queue.append(new_url)
            time.sleep(0.05)
        except Exception as exc:
            checked.append({"url": url, "error": repr(exc), "valid": False})

    # Award 2021 section discovery and extraction.
    award_pages = {}
    for prize in ("gold", "silver", "bronze"):
        url = f"{BASE}/2021/restaurants/{prize}"
        response = get(url)
        soup = BeautifulSoup(response.content, "lxml")
        restaurants = parse_restaurants(soup, response.url)
        award_pages[prize] = {
            "url": response.url,
            "status": response.status_code,
            "title": title_text(soup),
            "restaurant_count": len(restaurants),
            "restaurants": restaurants,
        }

    lists = sorted(successful.values(), key=lambda x: x["url"])
    manifest = {
        "year": int(YEAR),
        "hyakumeiten_list_count": len(lists),
        "hyakumeiten_total_slots": sum(item["restaurant_count"] for item in lists),
        "hyakumeiten_lists": [
            {k: item[k] for k in ("url", "title", "restaurant_count")} for item in lists
        ],
        "award_counts": {key: value["restaurant_count"] for key, value in award_pages.items()},
        "checked_url_count": len(checked),
    }

    (OUT / "discovery_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "hyakumeiten_2021_raw.json").write_text(
        json.dumps(lists, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "award_2021_raw.json").write_text(
        json.dumps(award_pages, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "checked_urls.json").write_text(
        json.dumps(checked, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
