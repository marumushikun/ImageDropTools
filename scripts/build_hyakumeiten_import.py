from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path('.')
SRC = ROOT / 'generated_hyakumeiten'
OUT = ROOT / 'generated_hyakumeiten_import'
OUT.mkdir(exist_ok=True)


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f, delimiter='\t'))


def write_tsv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


listings = read_tsv(SRC / 'hyakumeiten_2020_listings.tsv')
unique_stores = read_tsv(SRC / 'hyakumeiten_2020_unique_stores.tsv')
matches = read_tsv(ROOT / 'input' / 'hyakumeiten_2020_existing_matches.tsv')
match_by_tid = {row['tabelog_id']: row for row in matches}

assert len(listings) == 1905
assert len(unique_stores) == 1905
assert len(match_by_tid) == 53
assert len({x['tabelog_id'] for x in unique_stores}) == 1905

store_id_by_tid: dict[str, str] = {}
next_store_no = 822
new_store_rows: list[dict] = []
matched_store_rows: list[dict] = []

for row in unique_stores:
    tid = row['tabelog_id']
    if tid in match_by_tid:
        store_id = match_by_tid[tid]['store_id']
        store_id_by_tid[tid] = store_id
        matched_store_rows.append({
            'store_id': store_id,
            'tabelog_id': tid,
            'listed_name': row['listed_name'],
            'prefecture': row['prefecture'],
            'tabelog_url': row['tabelog_url'],
            'primary_genre': row['primary_genre'],
            'category_labels': row['category_labels'],
            'match_method': match_by_tid[tid]['match_method'],
        })
        continue

    store_id = f'FOD-{next_store_no:04d}'
    next_store_no += 1
    store_id_by_tid[tid] = store_id
    facility_type = 'ラーメン店' if row['primary_genre'] == 'ラーメン' else '飲食店'
    note = (
        f"食べログ 百名店 2020 / {row['category_labels']} / "
        f"Tabelog ID {tid} / {row['first_source_url']}"
    )
    new_store_rows.append({
        'store_id': store_id,
        '正式店名': row['listed_name'],
        '店名かな': '',
        '別名・旧名': '',
        '施設区分': facility_type,
        '大ジャンル': row['primary_genre'],
        '小ジャンル': f"食べログ {row['primary_genre']} 百名店 2020",
        '都道府県': row['prefecture'],
        '市区町村': '',
        '住所': '',
        '緯度': '',
        '経度': '',
        '最寄駅・交通': row['area_text'],
        '電話番号': '',
        '公式URL': '',
        '食べログURL': row['tabelog_url'],
        'GoogleマップURL': '',
        '営業状態': '未確認',
        '予約区分': '',
        '昼予算': '',
        '夜予算': '',
        '最終確認日': 46232,
        '確認状態': '店舗照合済',
        '備考': note,
    })

assert len(new_store_rows) == 1852, len(new_store_rows)
assert len(matched_store_rows) == 53, len(matched_store_rows)
assert new_store_rows[0]['store_id'] == 'FOD-0822'
assert new_store_rows[-1]['store_id'] == 'FOD-2673'
assert len(set(store_id_by_tid.values())) == 1905

award_rows: list[dict] = []
for i, row in enumerate(listings, start=1):
    store_id = store_id_by_tid[row['tabelog_id']]
    award_rows.append({
        'award_id': f'HYK2020-{i:04d}',
        'store_id': store_id,
        '選定元': '食べログ',
        '選定シリーズ': '食べログ 百名店',
        'ランク・区分': '百名店',
        '公式ジャンル': row['genre'],
        '年度': 2020,
        '地域区分': row['region'],
        '掲載名': row['listed_name'],
        '掲載時地域': row['prefecture'],
        '出典URL': row['source_url'],
        '出典確認日': 46232,
        '照合状態': '店舗照合済',
        '備考': (
            f"食べログ {row['genre']} {row['region']} 百名店 2020 / "
            f"公式掲載順 {row['category_ordinal']}/{row['category_official_count']} / "
            f"Tabelog ID {row['tabelog_id']}"
        ),
    })

assert len(award_rows) == 1905
assert award_rows[0]['award_id'] == 'HYK2020-0001'
assert award_rows[-1]['award_id'] == 'HYK2020-1905'
assert len({x['award_id'] for x in award_rows}) == 1905
assert all(x['store_id'] for x in award_rows)

store_fields = [
    'store_id','正式店名','店名かな','別名・旧名','施設区分','大ジャンル','小ジャンル','都道府県',
    '市区町村','住所','緯度','経度','最寄駅・交通','電話番号','公式URL','食べログURL',
    'GoogleマップURL','営業状態','予約区分','昼予算','夜予算','最終確認日','確認状態','備考',
]
award_fields = [
    'award_id','store_id','選定元','選定シリーズ','ランク・区分','公式ジャンル','年度','地域区分',
    '掲載名','掲載時地域','出典URL','出典確認日','照合状態','備考',
]
matched_fields = [
    'store_id','tabelog_id','listed_name','prefecture','tabelog_url','primary_genre','category_labels','match_method',
]

write_tsv(OUT / 'new_stores.tsv', store_fields, new_store_rows)
write_tsv(OUT / 'awards.tsv', award_fields, award_rows)
write_tsv(OUT / 'matched_existing_stores.tsv', matched_fields, matched_store_rows)

category_counts: dict[str, int] = {}
for row in award_rows:
    key = f"{row['公式ジャンル']} {row['地域区分']}"
    category_counts[key] = category_counts.get(key, 0) + 1

manifest = {
    'year': 2020,
    'genre_count': 7,
    'category_count': 19,
    'listing_count': len(award_rows),
    'existing_store_matches': len(matched_store_rows),
    'new_store_count': len(new_store_rows),
    'first_new_store_id': new_store_rows[0]['store_id'],
    'last_new_store_id': new_store_rows[-1]['store_id'],
    'first_award_id': award_rows[0]['award_id'],
    'last_award_id': award_rows[-1]['award_id'],
    'category_counts': category_counts,
}
(OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(manifest, ensure_ascii=False, indent=2))
