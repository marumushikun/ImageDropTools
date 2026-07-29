from __future__ import annotations

import csv
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
}


def clean_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path
    if not path.endswith("/"):
        path += "/"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def resolve(row: list[str]) -> dict[str, object]:
    store_id = row[0]
    name = row[1]
    prefecture = row[7]
    original = row[15]
    match = re.search(r"/(\d{6,})/?(?:\?.*)?$", original)
    if not match:
        return {"store_id": store_id, "name": name, "prefecture": prefecture, "original": original, "canonical": original, "method": "no-id", "ok": False}
    tid = match.group(1)

    # The public badge endpoint is keyed only by the restaurant code and often exposes the canonical path.
    try:
        badge_url = f"https://tabelog.com/badge/google_badge?escape=false&rcd={tid}"
        response = requests.get(badge_url, headers=HEADERS, timeout=45)
        text = response.text.replace("\\/", "/").replace("&amp;", "&")
        patterns = [
            rf"https?://tabelog\.com/[A-Za-z0-9_\-/]+/{tid}/",
            rf"https?://tabelog\.com/[A-Za-z0-9_\-/]+/{tid}",
        ]
        for pattern in patterns:
            found = re.search(pattern, text)
            if found:
                canonical = clean_url(found.group(0))
                return {"store_id": store_id, "name": name, "prefecture": prefecture, "original": original, "canonical": canonical, "method": "badge", "ok": True, "status": response.status_code}
    except Exception as error:
        badge_error = repr(error)
    else:
        badge_error = f"badge status={response.status_code} no canonical link"

    # Fallback: an area-mismatched historical link normally redirects to the canonical URL by restaurant code.
    try:
        response = requests.get(original, headers=HEADERS, timeout=45, allow_redirects=True, stream=True)
        final_url = clean_url(response.url)
        response.close()
        ok = tid in final_url and response.status_code < 500
        return {"store_id": store_id, "name": name, "prefecture": prefecture, "original": original, "canonical": final_url if ok else original, "method": "redirect" if ok else "fallback-original", "ok": ok, "status": response.status_code, "badge_error": badge_error}
    except Exception as error:
        return {"store_id": store_id, "name": name, "prefecture": prefecture, "original": original, "canonical": original, "method": "fallback-original", "ok": False, "badge_error": badge_error, "redirect_error": repr(error)}


source_path = Path("generated/foodie_stores.tsv")
with source_path.open(encoding="utf-8", newline="") as source:
    rows = list(csv.reader(source, delimiter="\t"))

results: list[dict[str, object] | None] = [None] * len(rows)
with ThreadPoolExecutor(max_workers=6) as executor:
    futures = {executor.submit(resolve, row): index for index, row in enumerate(rows)}
    for future in as_completed(futures):
        index = futures[future]
        results[index] = future.result()
        if (index + 1) % 25 == 0:
            print("resolved", index + 1, "/", len(rows))

resolved = [result for result in results if result is not None]
output_path = Path("generated/foodie_canonical_urls.tsv")
with output_path.open("w", encoding="utf-8", newline="") as output:
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    for result in resolved:
        writer.writerow([result["canonical"]])

stats = {
    "rows": len(resolved),
    "ok": sum(bool(result.get("ok")) for result in resolved),
    "failed": sum(not bool(result.get("ok")) for result in resolved),
    "methods": {},
}
for result in resolved:
    method = str(result.get("method"))
    stats["methods"][method] = stats["methods"].get(method, 0) + 1
Path("generated/foodie_canonical_urls.json").write_text(json.dumps({"stats": stats, "results": resolved}, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(stats, ensure_ascii=False))
