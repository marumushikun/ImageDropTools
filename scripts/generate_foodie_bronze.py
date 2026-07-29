from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 AppleWebKit/537.36 Chrome/130 Safari/537.36"}
MATCHED_TIDS = set("""1000022,10002097,1000457,1000645,1001719,1016052,1028665,1038603,12000422,12000598,12019424,12032785,13000145,13001179,13001228,13001593,13001625,13001664,13001944,13002088,13002111,13002260,13002285,13002514,13002897,13003509,13003531,13003708,13004426,13005316,13005853,13008700,13012243,13017765,13017947,13021036,13021521,13028856,13030881,13034857,13035339,13039787,13042074,13043684,13044361,13050216,13061640,13076544,13090866,13099830,13110652,13116523,13118905,13120294,13129298,13129390,13132399,13134663,13141364,13141888,13142028,13144681,13147391,13149065,13150975,13155925,13156479,13159782,13160021,13166325,13174951,13176396,13184367,13185496,13189075,13191105,13192025,13192399,13194346,13196268,13198197,13200027,13200186,13200286,13200559,13201105,13203027,13205840,13206559,13209611,13210722,13212953,13213150,13213368,13213748,13222093,13223613,13228116,13228902,14001626,14039956,17000107,2000121,21000011,21000060,21014394,22006811,23000105,23004080,23009279,23030549,23053940,23054325,26000305,26005825,26022527,26022648,26023402,27001141,27001233,27002614,27003367,27068283,27074473,27086016,28006575,29010346,30000104,3005625,31000300,32000061,4000130,4001636,40028665,40040809,41000056,44006115,45000157,5000004,5000308,5007142,7000278,7000810,7001326,8000180,9000024""".split(","))
REUSE_TID = "37000011"
REUSE_STORE_ID = "FOD-0021"
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


def get(url: str) -> bytes:
    response = requests.get(url, headers=HEADERS, timeout=90)
    response.raise_for_status()
    return response.content


def clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")


official: list[dict[str, object]] = []
for page_no in range(1, 6):
    suffix = "" if page_no == 1 else f"?page={page_no}"
    url = "https://award.tabelog.com/2020/restaurants/bronze" + suffix
    soup = BeautifulSoup(get(url), "lxml")
    cards = soup.select(".award2020-rstlst__item")
    print("page", page_no, "cards", len(cards))
    for card in cards:
        name_el = card.select_one(".award2020-rstlst__rst-name")
        en_el = card.select_one(".en-name")
        area_genre_el = card.select_one(".area-genre")
        link_el = card.select_one("a.award2020-rstlst__target")
        name = name_el.get_text(" ", strip=True) if name_el else ""
        en_name = en_el.get_text(" ", strip=True) if en_el else ""
        parts = [part.strip() for part in area_genre_el.get_text(" ", strip=True).split("/") if part.strip()] if area_genre_el else []
        area = parts[0] if parts else ""
        genre = parts[1] if len(parts) > 1 else ""
        href = link_el.get("href", "") if link_el else ""
        tid_match = re.search(r"/(\d{6,})/?(?:\?.*)?$", href)
        tid = tid_match.group(1) if tid_match else ""
        official.append({
            "name": name,
            "en_name": en_name,
            "genre": genre,
            "area_short": area,
            "prefecture": PREF.get(area, area),
            "tabelog_url": href,
            "tabelog_id": tid,
            "page": page_no,
        })

assert len(official) == 488, len(official)
for official_no, record in enumerate(official, start=1):
    record["official_no"] = official_no

archive_url = "https://raw.githubusercontent.com/iusmmf/tokyomap/3b34f2e6c9f49f1489eda0a605cde7d5ed647dc3/csv/2019/tabelog2019.csv"
archive_text = get(archive_url).decode("utf-8-sig")
archive_rows = list(csv.DictReader(archive_text.splitlines()))
tokyo_by_tid: dict[str, dict[str, str]] = {}
for row in archive_rows:
    match = re.search(r"/(\d{6,})/?$", row.get("URL", ""))
    if match:
        tokyo_by_tid[match.group(1)] = row

for record in official:
    if not record["tabelog_id"]:
        assert record["name"] == "ル・マノアール・ダスティン", record
        record["tabelog_id"] = "13000331"
        record["tabelog_url"] = "https://tabelog.com/tokyo/A1303/A130302/13000331/"

assert len({record["tabelog_id"] for record in official}) == 488
remaining = [record for record in official if record["tabelog_id"] not in MATCHED_TIDS]
assert len(remaining) == 342, len(remaining)
assert sum(record["tabelog_id"] == REUSE_TID for record in remaining) == 1

store_rows: list[list[object]] = []
award_rows: list[list[object]] = []
next_store = 481
for offset, record in enumerate(remaining):
    award_id = f"TBA2020-B-{147 + offset:03d}"
    if record["tabelog_id"] == REUSE_TID:
        store_id = REUSE_STORE_ID
    else:
        store_id = f"FOD-{next_store:04d}"
        next_store += 1

    award_rows.append([
        award_id, store_id, "食べログ", "The Tabelog Award", "Bronze",
        record["genre"], 2020, "全国", record["name"], record["prefecture"],
        "https://award.tabelog.com/2020/restaurants/bronze",
        46232, "店舗照合済",
        f"2020年Bronze受賞店（公式全488件名簿と照合済・公式掲載順 {record['official_no']}/488）",
    ])

    if store_id == REUSE_STORE_ID:
        continue

    archive = tokyo_by_tid.get(str(record["tabelog_id"]))
    city = archive.get("区", "") if archive else ""
    address = archive.get("住所", "") if archive else ""
    latitude = archive.get("緯度", "") if archive else ""
    longitude = archive.get("経度", "") if archive else ""
    tabelog_url = (archive.get("URL") if archive else "") or record["tabelog_url"]
    day_budget = archive.get("昼予算", "") if archive and archive.get("昼予算") not in ("-", None) else ""
    night_budget = archive.get("夜予算", "") if archive and archive.get("夜予算") not in ("-", None) else ""
    facility_type = "ラーメン店" if record["genre"] == "ラーメン" else "飲食店"
    note = (
        "The Tabelog Award 2020 Bronze / 公式受賞一覧全488件照合 / "
        f"公式掲載順 {record['official_no']}/488 / "
        "https://award.tabelog.com/2020/restaurants/bronze"
    )
    if archive:
        note += " / 東京アーカイブCSVで住所・座標・予算補完"

    store_rows.append([
        store_id, record["name"], "", "", facility_type, record["genre"],
        "The Tabelog Award 2020 Bronze", record["prefecture"], city, address,
        latitude, longitude, "", "", "", tabelog_url, "", "未確認", "",
        day_budget, night_budget, 46232, "店舗照合済", note,
    ])

assert len(store_rows) == 341
assert len(award_rows) == 342
assert store_rows[0][0] == "FOD-0481"
assert store_rows[-1][0] == "FOD-0821"
assert award_rows[0][0] == "TBA2020-B-147"
assert award_rows[-1][0] == "TBA2020-B-488"

output_dir = Path("generated")
output_dir.mkdir(exist_ok=True)
for filename, rows in (("foodie_stores.tsv", store_rows), ("foodie_awards.tsv", award_rows)):
    with (output_dir / filename).open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        writer.writerows([[clean(value) for value in row] for row in rows])

manifest = {
    "official_total": len(official),
    "already_registered": len(MATCHED_TIDS),
    "remaining_awards": len(award_rows),
    "new_stores": len(store_rows),
    "reused_store": {"tabelog_id": REUSE_TID, "store_id": REUSE_STORE_ID},
    "first_store_id": store_rows[0][0],
    "last_store_id": store_rows[-1][0],
    "first_award_id": award_rows[0][0],
    "last_award_id": award_rows[-1][0],
}
(output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(manifest, ensure_ascii=False))
