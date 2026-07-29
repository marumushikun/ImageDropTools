from __future__ import annotations

import csv
import json
import re
import time
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://award.tabelog.com"
YEAR = 2021
OUT = Path("generated_2021")
OUT.mkdir(exist_ok=True)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
}
PREF_FULL = {
    "北海道":"北海道","青森":"青森県","青森県":"青森県","岩手":"岩手県","岩手県":"岩手県",
    "宮城":"宮城県","宮城県":"宮城県","秋田":"秋田県","秋田県":"秋田県","山形":"山形県","山形県":"山形県",
    "福島":"福島県","福島県":"福島県","茨城":"茨城県","茨城県":"茨城県","栃木":"栃木県","栃木県":"栃木県",
    "群馬":"群馬県","群馬県":"群馬県","埼玉":"埼玉県","埼玉県":"埼玉県","千葉":"千葉県","千葉県":"千葉県",
    "東京":"東京都","東京都":"東京都","神奈川":"神奈川県","神奈川県":"神奈川県","新潟":"新潟県","新潟県":"新潟県",
    "富山":"富山県","富山県":"富山県","石川":"石川県","石川県":"石川県","福井":"福井県","福井県":"福井県",
    "山梨":"山梨県","山梨県":"山梨県","長野":"長野県","長野県":"長野県","岐阜":"岐阜県","岐阜県":"岐阜県",
    "静岡":"静岡県","静岡県":"静岡県","愛知":"愛知県","愛知県":"愛知県","三重":"三重県","三重県":"三重県",
    "滋賀":"滋賀県","滋賀県":"滋賀県","京都":"京都府","京都府":"京都府","大阪":"大阪府","大阪府":"大阪府",
    "兵庫":"兵庫県","兵庫県":"兵庫県","奈良":"奈良県","奈良県":"奈良県","和歌山":"和歌山県","和歌山県":"和歌山県",
    "鳥取":"鳥取県","鳥取県":"鳥取県","島根":"島根県","島根県":"島根県","岡山":"岡山県","岡山県":"岡山県",
    "広島":"広島県","広島県":"広島県","山口":"山口県","山口県":"山口県","徳島":"徳島県","徳島県":"徳島県",
    "香川":"香川県","香川県":"香川県","愛媛":"愛媛県","愛媛県":"愛媛県","高知":"高知県","高知県":"高知県",
    "福岡":"福岡県","福岡県":"福岡県","佐賀":"佐賀県","佐賀県":"佐賀県","長崎":"長崎県","長崎県":"長崎県",
    "熊本":"熊本県","熊本県":"熊本県","大分":"大分県","大分県":"大分県","宮崎":"宮崎県","宮崎県":"宮崎県",
    "鹿児島":"鹿児島県","鹿児島県":"鹿児島県","沖縄":"沖縄県","沖縄県":"沖縄県",
}

session = requests.Session()
session.headers.update(HEADERS)


def get(url: str) -> requests.Response:
    response = session.get(url, timeout=90, allow_redirects=True)
    response.raise_for_status()
    return response


def tid_from_url(url: str) -> str:
    match = re.search(r"/(\d{6,})/?(?:[?#].*)?$", url)
    return match.group(1) if match else ""


def normalize_name(value: str) -> str:
    return re.sub(r"[\s　・･'’\"“”‐‑‒–—―ーｰ]+", "", value or "").lower()


def store_key(tid: str, name: str, prefecture: str) -> str:
    return tid if tid else f"NAME:{normalize_name(name)}|{prefecture}"


def clean(value) -> str:
    if value is None:
        return ""
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def write_tsv(path: Path, rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        writer.writerows([[clean(value) for value in row] for row in rows])


def parse_list_label(title: str) -> tuple[str, str]:
    label = re.sub(r"^食べログ\s+", "", title)
    label = re.sub(r"\s+百名店\s+2021.*$", "", label).strip()
    for region in ("TOKYO", "EAST", "WEST", "KAGAWA"):
        suffix = " " + region
        if label.endswith(suffix):
            return label[:-len(suffix)].strip(), region
    return label, "全国"


def parse_hyakumeiten(url: str) -> dict:
    response = get(url)
    soup = BeautifulSoup(response.content, "lxml")
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    genre, region = parse_list_label(title)
    records = []
    cards = soup.select("div.hyakumeiten-shop__item")
    for order, card in enumerate(cards, start=1):
        anchor = card.select_one("a.hyakumeiten-shop__target")
        href = urljoin(response.url, anchor.get("href", "")) if anchor else ""
        tid = tid_from_url(href)
        name_node = card.select_one(".hyakumeiten-shop__name")
        area_node = card.select_one(".hyakumeiten-shop__area")
        name = name_node.get_text(" ", strip=True) if name_node else ""
        area = area_node.get_text(" ", strip=True) if area_node else ""
        name = re.sub(r"^初選出\s*", "", name).strip()
        pref_token = area.split()[0] if area else ""
        prefecture = PREF_FULL.get(pref_token, pref_token)
        station = " ".join(area.split()[1:]) if area else ""
        records.append({
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
            "store_key": store_key(tid, name, prefecture),
            "source_url": response.url.split("?",1)[0].rstrip("/"),
            "official_order": order,
            "special": "",
        })
    assert len(records) == 100, f"{url}: expected 100 official cards, got {len(records)}"
    assert all(r["name"] and r["prefecture"] and r["store_key"] for r in records), url
    return {"url": response.url.split("?",1)[0].rstrip("/"), "title": title, "genre": genre, "region": region, "records": records}


def parse_award_prize(prize: str) -> list[dict]:
    all_records = []
    seen = set()
    for page_no in range(1, 20):
        base = f"{BASE}/{YEAR}/restaurants/{prize}"
        url = base if page_no == 1 else f"{base}?page={page_no}"
        response = get(url)
        soup = BeautifulSoup(response.content, "lxml")
        anchors = soup.select("a.award2021-rstlst__target")
        page_new = 0
        for anchor in anchors:
            href = urljoin(response.url, anchor.get("href", ""))
            tid = tid_from_url(href)
            if not tid or tid in seen:
                continue
            card = anchor.find_parent("li", class_="award2021-rstlst__item") or anchor
            name_node = card.select_one(".award2021-rstlst__rst-name")
            area_genre_node = card.select_one(".award2021-rstlst__area-genre")
            name = name_node.get_text(" ", strip=True) if name_node else ""
            area_genre = area_genre_node.get_text(" ", strip=True) if area_genre_node else ""
            parts = [part.strip() for part in area_genre.rsplit("/", 1)]
            genre = parts[0] if parts else ""
            area = parts[1] if len(parts) > 1 else ""
            prefecture = PREF_FULL.get(area, area)
            blob = card.get_text(" ", strip=True).upper()
            specials = []
            if "BEST NEW ENTRY" in blob:
                specials.append("Best New Entry")
            if "BEST REGIONAL RESTAURANTS" in blob:
                specials.append("Best Regional Restaurants")
            if "CHEFS' GOLD" in blob or "CHEFS’ GOLD" in blob:
                specials.append("Chefs' Gold")
            seen.add(tid)
            page_new += 1
            all_records.append({
                "kind": "Award",
                "list_title": "The Tabelog Award",
                "award_class": prize.capitalize(),
                "genre": genre,
                "region": "全国",
                "name": name,
                "prefecture": prefecture,
                "station": "",
                "tabelog_url": href,
                "tabelog_id": tid,
                "store_key": store_key(tid, name, prefecture),
                "source_url": base,
                "official_order": len(all_records) + 1,
                "special": " / ".join(specials),
            })
        if page_new == 0:
            break
        if len(anchors) < 100:
            break
        time.sleep(0.05)
    assert len(all_records) >= 20, f"award {prize}: suspicious count {len(all_records)}"
    assert all(r["name"] and r["prefecture"] and r["genre"] for r in all_records), prize
    return all_records


def main() -> None:
    discovery = json.loads((OUT / "discovery_manifest.json").read_text(encoding="utf-8"))
    list_urls = [item["url"] for item in discovery["hyakumeiten_lists"]]
    assert len(list_urls) == 32, f"expected 32 discovered 2021 lists, got {len(list_urls)}"

    hyak_lists = [parse_hyakumeiten(url) for url in list_urls]
    hyak_records = [record for item in hyak_lists for record in item["records"]]
    assert len(hyak_records) == 3200

    award_by_prize = {prize: parse_award_prize(prize) for prize in ("gold", "silver", "bronze")}
    award_records = [record for prize in ("gold", "silver", "bronze") for record in award_by_prize[prize]]

    history_rows = []
    for index, record in enumerate(hyak_records, start=1):
        history_rows.append([
            f"HYK2021-{index:04d}", record["store_key"], "食べログ", record["list_title"], "百名店",
            record["genre"], YEAR, record["region"], record["name"], record["prefecture"],
            record["source_url"], 46232, "店舗照合済",
            f"2021年百名店公式選出（{record['list_title']} {record['region']}・公式掲載順 {record['official_order']}/100）",
        ])

    prize_prefix = {"Gold":"G", "Silver":"S", "Bronze":"B"}
    prize_counters = {"Gold":0, "Silver":0, "Bronze":0}
    for record in award_records:
        prize = record["award_class"]
        prize_counters[prize] += 1
        history_rows.append([
            f"TBA2021-{prize_prefix[prize]}-{prize_counters[prize]:03d}", record["store_key"], "食べログ",
            "The Tabelog Award", prize, record["genre"], YEAR, "全国", record["name"], record["prefecture"],
            record["source_url"], 46232, "店舗照合済",
            f"The Tabelog Award 2021 {prize}（公式掲載順 {record['official_order']}）" + (f" / {record['special']}" if record['special'] else ""),
        ])

    unique = OrderedDict()
    for record in award_records + hyak_records:
        key = record["store_key"]
        if key not in unique:
            unique[key] = record.copy()
        else:
            current = unique[key]
            if not current.get("genre") and record.get("genre"):
                current["genre"] = record["genre"]
            if not current.get("prefecture") and record.get("prefecture"):
                current["prefecture"] = record["prefecture"]
            if not current.get("station") and record.get("station"):
                current["station"] = record["station"]
            if not current.get("tabelog_url") and record.get("tabelog_url"):
                current["tabelog_url"] = record["tabelog_url"]
                current["tabelog_id"] = record["tabelog_id"]

    store_rows = []
    for key, record in unique.items():
        facility_type = "ラーメン店" if record["genre"] == "ラーメン" else "飲食店"
        store_rows.append([
            key, record["tabelog_id"], record["name"], record["prefecture"], facility_type, record["genre"],
            record["station"], record["tabelog_url"], record["source_url"],
            "The Tabelog Award / 百名店 2021 公式名簿候補",
        ])

    write_tsv(OUT / "stores_2021.tsv", store_rows)
    write_tsv(OUT / "histories_2021.tsv", history_rows)

    special_counts = {}
    for record in award_records:
        for special in [s.strip() for s in record["special"].split("/") if s.strip()]:
            special_counts[special] = special_counts.get(special, 0) + 1

    manifest = {
        "year": YEAR,
        "hyakumeiten": {
            "list_count": len(hyak_lists),
            "history_count": len(hyak_records),
            "lists": [
                {"url": item["url"], "title": item["title"], "genre": item["genre"], "region": item["region"], "count": len(item["records"]), "url_missing": sum(1 for r in item["records"] if not r["tabelog_id"])}
                for item in hyak_lists
            ],
        },
        "award": {
            "counts": {prize.capitalize(): len(records) for prize, records in award_by_prize.items()},
            "total": len(award_records),
            "special_counts": special_counts,
        },
        "total_history_rows": len(history_rows),
        "unique_store_candidates": len(store_rows),
        "first_history_id": history_rows[0][0],
        "last_history_id": history_rows[-1][0],
        "url_missing_history_count": sum(1 for r in hyak_records if not r["tabelog_id"]),
        "blank_names": sum(1 for row in store_rows if not row[2]),
        "blank_prefectures": sum(1 for row in store_rows if not row[3]),
        "duplicate_store_keys": len(store_rows) - len({row[0] for row in store_rows}),
    }
    assert manifest["blank_names"] == 0
    assert manifest["blank_prefectures"] == 0
    assert manifest["duplicate_store_keys"] == 0
    (OUT / "verified_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
