from __future__ import annotations

import csv
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 AppleWebKit/537.36 Chrome/130 Safari/537.36"}
PREF = {
    "北海道": "北海道", "青森": "青森県", "岩手": "岩手県", "宮城": "宮城県", "秋田": "秋田県",
    "山形": "山形県", "福島": "福島県", "茨城": "茨城県", "栃木": "栃木県", "群馬": "群馬県",
    "埼玉": "埼玉県", "千葉": "千葉県", "東京": "東京都", "神奈川": "神奈川県", "新潟": "新潟県",
    "富山": "富山県", "石川": "石川県", "福井": "福井県", "山梨": "山梨県", "長野": "長野県",
    "岐阜": "岐阜県", "静岡": "静岡県", "愛知": "愛知県", "三重": "三重県", "滋賀": "滋賀県",
    "京都": "京都府", "大阪": "大阪府", "兵庫": "兵庫県", "奈良": "奈良県", "和歌山": "和歌山県",
    "鳥取": "鳥取県", "島根": "島根県", "岡山": "岡山県", "広島": "広島県", "山口": "山口県",
    "徳島": "徳島県", "香川": "香川県", "愛媛": "愛媛県", "高知": "高知県", "福岡": "福岡県",
    "佐賀": "佐賀県", "長崎": "長崎県", "熊本": "熊本県", "大分": "大分県", "宮崎": "宮崎県",
    "鹿児島": "鹿児島県", "沖縄": "沖縄県",
}

by_name: dict[str, tuple[str, str]] = {}
for page_no in range(1, 6):
    suffix = "" if page_no == 1 else f"?page={page_no}"
    response = requests.get(
        "https://award.tabelog.com/2020/restaurants/bronze" + suffix,
        headers=HEADERS,
        timeout=90,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "lxml")
    for card in soup.select(".award2020-rstlst__item"):
        name_el = card.select_one(".award2020-rstlst__rst-name")
        area_genre_el = card.select_one(".award2020-rstlst__area-genre")
        name = name_el.get_text(" ", strip=True) if name_el else ""
        parts = [part.strip() for part in area_genre_el.get_text(" ", strip=True).split("/") if part.strip()] if area_genre_el else []
        genre = parts[0] if parts else ""
        area = parts[1] if len(parts) > 1 else ""
        by_name[name] = (genre, PREF.get(area, area))

assert len(by_name) == 488, len(by_name)

stores_path = Path("generated/foodie_stores.tsv")
with stores_path.open(encoding="utf-8", newline="") as source:
    store_rows = list(csv.reader(source, delimiter="\t"))
for row in store_rows:
    genre, prefecture = by_name[row[1]]
    row[4] = "ラーメン店" if genre == "ラーメン" else "飲食店"
    row[5] = genre
    row[7] = prefecture
with stores_path.open("w", encoding="utf-8", newline="") as output:
    csv.writer(output, delimiter="\t", lineterminator="\n").writerows(store_rows)

awards_path = Path("generated/foodie_awards.tsv")
with awards_path.open(encoding="utf-8", newline="") as source:
    award_rows = list(csv.reader(source, delimiter="\t"))
for row in award_rows:
    genre, prefecture = by_name[row[8]]
    row[5] = genre
    row[9] = prefecture
with awards_path.open("w", encoding="utf-8", newline="") as output:
    csv.writer(output, delimiter="\t", lineterminator="\n").writerows(award_rows)

assert all(row[5] and row[7] for row in store_rows)
assert all(row[5] and row[9] for row in award_rows)
print("patched", len(store_rows), len(award_rows))
