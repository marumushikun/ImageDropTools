from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://award.tabelog.com"
YEAR = 2021
OUT = Path("generated_2021")
OUT.mkdir(exist_ok=True)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
}

PREF_BY_SLUG = {
    "hokkaido": "北海道", "aomori": "青森県", "iwate": "岩手県", "miyagi": "宮城県", "akita": "秋田県",
    "yamagata": "山形県", "fukushima": "福島県", "ibaraki": "茨城県", "tochigi": "栃木県", "gunma": "群馬県",
    "saitama": "埼玉県", "chiba": "千葉県", "tokyo": "東京都", "kanagawa": "神奈川県", "niigata": "新潟県",
    "toyama": "富山県", "ishikawa": "石川県", "fukui": "福井県", "yamanashi": "山梨県", "nagano": "長野県",
    "gifu": "岐阜県", "shizuoka": "静岡県", "aichi": "愛知県", "mie": "三重県", "shiga": "滋賀県",
    "kyoto": "京都府", "osaka": "大阪府", "hyogo": "兵庫県", "nara": "奈良県", "wakayama": "和歌山県",
    "tottori": "鳥取県", "shimane": "島根県", "okayama": "岡山県", "hiroshima": "広島県", "yamaguchi": "山口県",
    "tokushima": "徳島県", "kagawa": "香川県", "ehime": "愛媛県", "kochi": "高知県", "fukuoka": "福岡県",
    "saga": "佐賀県", "nagasaki": "長崎県", "kumamoto": "熊本県", "oita": "大分県", "miyazaki": "宮崎県",
    "kagoshima": "鹿児島県", "okinawa": "沖縄県",
}

GENRES = [
    "焼肉・すき焼き・しゃぶしゃぶ", "魚介料理・海鮮料理", "ステーキ・鉄板焼き", "焼き鳥・鳥料理",
    "アジア・エスニック", "イノベーティブ", "スペイン料理", "中華料理", "日本料理", "フレンチ",
    "イタリアン", "創作料理", "うなぎ", "そば", "寿司", "天ぷら", "焼肉", "ラーメン",
]

session = requests.Session()
session.headers.update(HEADERS)


def get(url: str) -> requests.Response:
    r = session.get(url, timeout=90, allow_redirects=True)
    r.raise_for_status()
    return r


def tabelog_id(url: str) -> str:
    m = re.search(r"/(\d{6,})/?(?:[?#].*)?$", url)
    return m.group(1) if m else ""


def prefecture_from_url(url: str) -> str:
    try:
        parts = urlparse(url).path.strip("/").split("/")
        return PREF_BY_SLUG.get(parts[0], "") if parts else ""
    except Exception:
        return ""


def parse_restaurants(soup: BeautifulSoup, page_url: str) -> list[dict]:
    found: dict[str, dict] = {}
    for anchor in soup.select("a[href]"):
        href = urljoin(page_url, anchor.get("href", ""))
        if "tabelog.com/" not in href:
            continue
        tid = tabelog_id(href)
        if not tid:
            continue

        node = anchor
        card = anchor
        for _ in range(7):
            if node.parent is None:
                break
            node = node.parent
            class_text = " ".join(node.get("class", []))
            card = node
            if any(token in class_text.lower() for token in ("item", "card", "list", "rst")):
                break

        name = anchor.get_text(" ", strip=True)
        candidates: list[str] = []
        for sel in (
            ".award2021-rstlst__rst-name", ".award-rstlst__rst-name", ".hyakumeiten-rst-list__rst-name",
            ".rst-name", ".restaurant-name", "h2", "h3", "h4", "strong",
        ):
            n = card.select_one(sel) if card else None
            if n:
                text = n.get_text(" ", strip=True)
                if 1 < len(text) <= 100:
                    candidates.append(text)
        if card:
            for n in card.select("a, h2, h3, h4, strong"):
                text = n.get_text(" ", strip=True)
                if 1 < len(text) <= 80 and text not in {"食べログ", "詳細", "公式ページ", "口コミ"}:
                    candidates.append(text)
        if candidates:
            candidates = sorted(set(candidates), key=lambda x: ("駅" in x or "県" in x, len(x)))
            if not name or len(name) > 100 or len(candidates[0]) < len(name):
                name = candidates[0]

        blob = card.get_text(" ", strip=True)[:600] if card else name
        genre = ""
        for candidate in GENRES:
            if candidate in blob:
                genre = candidate
                break

        rec = {
            "name": name.strip(),
            "tabelog_url": href.split("?", 1)[0],
            "tabelog_id": tid,
            "prefecture": prefecture_from_url(href),
            "genre": genre,
            "text": blob,
        }
        old = found.get(tid)
        if old is None or (len(rec["name"]) < len(old.get("name", "")) and rec["name"]):
            found[tid] = rec
    return list(found.values())


def parse_hyakumeiten_title(title: str, url: str) -> tuple[str, str]:
    cleaned = re.sub(r"\s*\[食べログ\]\s*$", "", title).strip()
    cleaned = re.sub(r"^食べログ\s+", "", cleaned)
    cleaned = re.sub(r"\s+百名店\s+2021$", "", cleaned).strip()
    region = "全国"
    for token in ("TOKYO", "EAST", "WEST"):
        if cleaned.endswith(" " + token):
            cleaned = cleaned[: -(len(token) + 1)].strip()
            region = token
            break
    return cleaned, region


def collect_award(prize: str) -> list[dict]:
    combined: dict[str, dict] = {}
    for page_no in range(1, 21):
        suffix = "" if page_no == 1 else f"?page={page_no}"
        url = f"{BASE}/2021/restaurants/{prize}{suffix}"
        r = get(url)
        soup = BeautifulSoup(r.content, "lxml")
        rows = parse_restaurants(soup, r.url)
        new_count = 0
        for row in rows:
            if row["tabelog_id"] not in combined:
                combined[row["tabelog_id"]] = row
                new_count += 1
        print("award", prize, page_no, len(rows), new_count, len(combined))
        if not rows or new_count == 0 or len(rows) < 100:
            break
        time.sleep(0.05)
    result = list(combined.values())
    result.sort(key=lambda x: (x["name"], x["tabelog_id"]))
    return result


def clean(value: object) -> str:
    return str(value if value is not None else "").replace("\t", " ").replace("\r", " ").replace("\n", " ")


def main() -> None:
    hyaku_path = OUT / "hyakumeiten_2021_raw.json"
    if not hyaku_path.exists():
        raise FileNotFoundError(hyaku_path)
    hyaku_lists = json.loads(hyaku_path.read_text(encoding="utf-8"))

    all_rows: list[list[object]] = []
    manifest_lists: list[dict] = []

    for item in sorted(hyaku_lists, key=lambda x: x["url"]):
        genre, region = parse_hyakumeiten_title(item["title"], item["url"])
        rows = item["restaurants"]
        total = len(rows)
        for seq, row in enumerate(rows, start=1):
            all_rows.append([
                "百名店", "百名店", genre, region, row["name"], row.get("prefecture") or prefecture_from_url(row["tabelog_url"]),
                item["url"], row["tabelog_url"], row["tabelog_id"], seq, total, item["title"], row.get("text", ""),
            ])
        manifest_lists.append({"kind": "百名店", "genre": genre, "region": region, "url": item["url"], "count": total})

    award_counts: dict[str, int] = {}
    prize_labels = {"gold": "Gold", "silver": "Silver", "bronze": "Bronze"}
    for prize in ("gold", "silver", "bronze"):
        rows = collect_award(prize)
        total = len(rows)
        award_counts[prize_labels[prize]] = total
        source_url = f"{BASE}/2021/restaurants/{prize}"
        for seq, row in enumerate(rows, start=1):
            all_rows.append([
                "The Tabelog Award", prize_labels[prize], row.get("genre", ""), "全国", row["name"], row.get("prefecture", ""),
                source_url, row["tabelog_url"], row["tabelog_id"], seq, total, f"The Tabelog Award 2021 {prize_labels[prize]}", row.get("text", ""),
            ])
        manifest_lists.append({"kind": "The Tabelog Award", "prize": prize_labels[prize], "url": source_url, "count": total})

    header = [
        "record_kind", "award_category", "genre", "region", "name", "prefecture", "source_url", "tabelog_url",
        "tabelog_id", "source_seq", "source_total", "source_title", "raw_text",
    ]
    with (OUT / "official_2021_all.tsv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(header)
        w.writerows([[clean(v) for v in row] for row in all_rows])

    manifest = {
        "year": YEAR,
        "hyakumeiten_list_count": len(hyaku_lists),
        "hyakumeiten_total_slots": sum(x["count"] for x in manifest_lists if x["kind"] == "百名店"),
        "award_counts": award_counts,
        "award_total": sum(award_counts.values()),
        "all_history_rows": len(all_rows),
        "lists": manifest_lists,
        "unique_tabelog_ids": len({str(row[8]) for row in all_rows}),
    }
    (OUT / "official_2021_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
