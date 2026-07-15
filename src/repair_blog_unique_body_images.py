from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests
import urllib3

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fill_horoshop_content_pages import load_env, parse_form_payload


urllib3.disable_warnings()

ROOT = Path(r"D:\FISH\fish-sync")
VISUALS_REPORT = ROOT / "data" / "horoshop_category_visuals_report.json"
REPORT = ROOT / "data" / "blog_unique_body_images_repair_20260602.json"


def load_uploads() -> dict[str, str]:
    data = json.loads(VISUALS_REPORT.read_text(encoding="utf-8"))
    return {key: value["uri"] for key, value in data.get("uploads", {}).items() if value.get("uri")}


UPLOADS = load_uploads()
UNIQUE_KEYS = [
    key for key in sorted(UPLOADS)
    if key.startswith("cat_unique_")
]


def retry_get(session: requests.Session, url: str, **kwargs):
    for attempt in range(5):
        try:
            return session.get(url, **kwargs)
        except requests.RequestException:
            if attempt == 4:
                raise
            time.sleep(2 + attempt)


def retry_post(session: requests.Session, url: str, **kwargs):
    for attempt in range(5):
        try:
            return session.post(url, **kwargs)
        except requests.RequestException:
            if attempt == 4:
                raise
            time.sleep(2 + attempt)


def active_blog_records(session: requests.Session, base_url: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for record_id in range(1, 180):
        edit_url = f"{base_url}/adminLegacy/edit.php?id={record_id}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
        response = retry_get(session, edit_url, timeout=60, verify=False)
        if response.status_code != 200 or "h_news" not in response.text:
            continue
        payload = parse_form_payload(response.text)
        if payload.get("names[act]") != "1":
            continue
        title = payload.get("names[i18n][3][title]", "")
        slug = payload.get("names[name][slug]", "")
        if not title or not slug:
            continue
        records.append(
            {
                "id": str(record_id),
                "title": title,
                "slug": slug,
                "preview": payload.get("names[img][value]", ""),
            }
        )
    return records


def choose_keys(records: list[dict[str, str]]) -> dict[str, tuple[str, str]]:
    assignments: dict[str, tuple[str, str]] = {}
    used: set[str] = set()
    for index, record in enumerate(records):
        preview_tail = Path(record["preview"]).name if record.get("preview") else ""
        preferred = ""
        for key in UNIQUE_KEYS:
            if Path(UPLOADS[key]).name == preview_tail:
                preferred = key
                break
        if not preferred:
            preferred = UNIQUE_KEYS[index % len(UNIQUE_KEYS)]
        if preferred in used:
            for key in UNIQUE_KEYS:
                if key not in used:
                    preferred = key
                    break
        used.add(preferred)
        secondary = ""
        for offset in range(17, len(UNIQUE_KEYS) + 17):
            candidate = UNIQUE_KEYS[(index + offset) % len(UNIQUE_KEYS)]
            if candidate != preferred and candidate not in used:
                secondary = candidate
                break
        if not secondary:
            for candidate in UNIQUE_KEYS:
                if candidate != preferred:
                    secondary = candidate
                    break
        used.add(secondary)
        assignments[record["id"]] = (preferred, secondary)
    return assignments


def replace_article_images(body: str, first_url: str, second_url: str, title: str) -> str:
    fig_pattern = re.compile(r'<figure class="content-figure">.*?</figure>', flags=re.I | re.S)
    new_first = (
        '<figure class="content-figure">'
        f'<img src="{first_url}" alt="{title}" loading="lazy">'
        f'<figcaption>{title}</figcaption>'
        "</figure>"
    )
    new_second = (
        '<figure class="content-figure">'
        f'<img src="{second_url}" alt="{title}: практичний приклад спорядження" loading="lazy">'
        f'<figcaption>{title}: практичний приклад спорядження</figcaption>'
        "</figure>"
    )
    figures = fig_pattern.findall(body)
    if len(figures) >= 2:
        body = fig_pattern.sub(lambda match, c=iter([new_first, new_second]): next(c, match.group(0)), body, count=2)
    elif len(figures) == 1:
        body = fig_pattern.sub(new_first, body, count=1)
        body = body.replace("</h2>", "</h2>\n" + new_second, 1)
    else:
        body = new_first + "\n" + new_second + "\n" + body
    body = body.replace("https://vsedliarybalky.com.ua/images/editor/2/water.jpg", second_url)
    return body


def image_counter(records: list[dict[str, str]], session: requests.Session, base_url: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        edit_url = f"{base_url}/adminLegacy/edit.php?id={record['id']}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
        response = retry_get(session, edit_url, timeout=60, verify=False)
        payload = parse_form_payload(response.text)
        body = payload.get("names[i18n][3][text]", "")
        for src in re.findall(r'<img[^>]+src=["\']([^"\']+)', body, flags=re.I):
            counts[src] = counts.get(src, 0) + 1
    return counts


def main() -> int:
    env = load_env()
    base_url = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    session = requests.Session()
    session.headers["User-Agent"] = "fish-blog-unique-body-images/1.0"
    session.post(
        f"{base_url}/core-api/admin/security/login",
        json={"login": env["HOROSHOP_LOGIN"], "password": env["HOROSHOP_PASS"]},
        timeout=60,
        verify=False,
    ).raise_for_status()

    records = active_blog_records(session, base_url)
    records.sort(key=lambda item: int(item["id"]))
    assignments = choose_keys(records)
    updated = []
    for record in records:
        first_key, second_key = assignments[record["id"]]
        first_url = UPLOADS[first_key]
        second_url = UPLOADS[second_key]
        edit_url = f"{base_url}/adminLegacy/edit.php?id={record['id']}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
        response = retry_get(session, edit_url, timeout=60, verify=False)
        response.raise_for_status()
        payload = parse_form_payload(response.text)
        body = payload.get("names[i18n][3][text]", "")
        new_body = replace_article_images(body, first_url, second_url, record["title"])
        payload.update(
            {
                "checkcode": "yamete_kudasai",
                "id": record["id"],
                "handler": "172",
                "handlertable": "h_news",
                "back": "index.php",
                "names[act]": "1",
                "names[parent]": "1001",
                "names[i18n][3][text]": new_body,
            }
        )
        save = retry_post(
            session,
            f"{base_url}/adminLegacy/save.php",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": edit_url},
            timeout=90,
            verify=False,
            allow_redirects=True,
        )
        save.raise_for_status()
        updated.append(
            {
                "id": record["id"],
                "title": record["title"],
                "first_key": first_key,
                "second_key": second_key,
                "first_url": first_url,
                "second_url": second_url,
                "status": save.status_code,
            }
        )
        time.sleep(0.15)

    counts = image_counter(records, session, base_url)
    duplicates = {src: count for src, count in counts.items() if count > 1}
    report = {
        "active_count": len(records),
        "updated_count": len(updated),
        "updated": updated,
        "unique_body_images": len(counts),
        "duplicate_body_images": duplicates,
        "water_count": counts.get("https://vsedliarybalky.com.ua/images/editor/2/water.jpg", 0),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "active_count": report["active_count"],
        "updated_count": report["updated_count"],
        "unique_body_images": report["unique_body_images"],
        "duplicate_body_images": report["duplicate_body_images"],
        "water_count": report["water_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
