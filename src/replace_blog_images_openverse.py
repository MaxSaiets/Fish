from __future__ import annotations

import html
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
import urllib3
from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fill_horoshop_content_pages import load_env, parse_form_payload


urllib3.disable_warnings()

ROOT = Path(r"D:\FISH\fish-sync")
OUT_DIR = ROOT / "public" / "blog-openverse-images"
REPORT = ROOT / "data" / "blog_openverse_image_replacement_20260602.json"


QUERY_RULES: list[tuple[str, str]] = [
    ("спінінг|спінінга|воблер|воблери|блешні|силіконові|приман", "fishing lure fishing rod"),
    ("фідер|годівниці|метод", "feeder fishing tackle"),
    ("короп|бойли|pop-up|макуха|пелетс", "carp fishing bait"),
    ("прикорм|дипи|ліквіди|атрактанти|насад", "fishing bait tackle"),
    ("гачки|флюорокарбон|волосінь|шнур|повідковий|карабіни|вертлюги|грузила|монтаж", "fishing tackle hooks line"),
    ("pva", "carp fishing pva bait"),
    ("зимова|мормишки|балансири|жерлиці|лід", "ice fishing"),
    ("котушка|котушки", "fishing reel"),
    ("коробки|органайзери|сумки|чохли|тубуси", "fishing tackle box bag"),
    ("доставка|самовивіз|чек-лист|подарунок|характеристики", "fishing gear"),
    ("підсаки|садки|кукани", "fishing net"),
    ("крісла|столи|туристичне|плити|пальники|посуд", "camping fishing"),
    ("поплавкова|махові|болонське|поплавок", "float fishing"),
    ("сигналізатори|ліхтарі|нічна", "night fishing gear"),
    ("запчастини|вудилищ", "fishing rod close up"),
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


def query_for_title(title: str) -> str:
    normalized = title.lower()
    for pattern, query in QUERY_RULES:
        if re.search(pattern, normalized):
            return query
    return "fishing tackle"


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
        if title and slug:
            records.append({"id": str(record_id), "title": title, "slug": slug})
    return records


def openverse_candidates(query: str, pages: int = 6) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-openverse-blog/1.0"
    for page in range(1, pages + 1):
        response = retry_get(
            session,
            "https://api.openverse.engineering/v1/images/",
            params={
                "q": query,
                "license": "cc0,pdm",
                "page_size": 20,
                "page": page,
            },
            timeout=45,
        )
        if response.status_code != 200:
            continue
        for item in response.json().get("results", []):
            url = str(item.get("url") or "")
            if not url or url in seen:
                continue
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                continue
            if not re.search(r"\.(jpe?g|png|webp)(\?|$)", url, flags=re.I):
                continue
            seen.add(url)
            results.append(
                {
                    "url": url,
                    "title": str(item.get("title") or ""),
                    "foreign_landing_url": str(item.get("foreign_landing_url") or ""),
                    "license": str(item.get("license") or ""),
                    "creator": str(item.get("creator") or ""),
                    "source": str(item.get("source") or ""),
                }
            )
    return results


def collect_candidates(records: list[dict[str, str]], needed: int) -> list[dict[str, str]]:
    query_order = []
    for record in records:
        query = query_for_title(record["title"])
        if query not in query_order:
            query_order.append(query)
    query_order.extend(["fishing tackle", "fishing rod", "fishing reel", "carp fishing", "ice fishing", "fishing lure", "camping fishing"])

    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    for query in query_order:
        for item in openverse_candidates(query):
            if item["url"] not in seen:
                seen.add(item["url"])
                item["query"] = query
                candidates.append(item)
            if len(candidates) >= needed:
                return candidates
    return candidates


def download_and_prepare(item: dict[str, str], target: Path, index: int) -> dict[str, object] | None:
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (compatible; fish-sync-openverse-blog/1.0)"
    try:
        response = retry_get(session, item["url"], timeout=60, stream=True)
        response.raise_for_status()
        raw = response.content
        if len(raw) < 20_000:
            return None
        source_path = target.with_suffix(".source")
        source_path.write_bytes(raw)
        image = Image.open(source_path).convert("RGB")
        if image.width < 500 or image.height < 350:
            return None
        center_x = 0.45 + ((index % 5) * 0.025)
        center_y = 0.48 + ((index % 3) * 0.03)
        image = ImageOps.fit(image, (1200, 800), method=Image.Resampling.LANCZOS, centering=(min(center_x, 0.58), min(center_y, 0.6)))
        image = ImageEnhance.Color(image).enhance(1.04)
        image = ImageEnhance.Contrast(image).enhance(1.04)
        image.save(target, "JPEG", quality=86, optimize=True, progressive=True)
        return {**item, "local_path": str(target), "source_size": [image.width, image.height]}
    except (requests.RequestException, UnidentifiedImageError, OSError):
        return None


def prepare_images(candidates: list[dict[str, str]], count: int) -> list[dict[str, object]]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prepared: list[dict[str, object]] = []
    for idx, item in enumerate(candidates):
        if len(prepared) >= count:
            break
        target = OUT_DIR / f"blog_openverse_{len(prepared)+1:03d}.jpg"
        prepared_item = download_and_prepare(item, target, idx)
        if prepared_item:
            prepared.append(prepared_item)
    return prepared


def upload_editor_image(session: requests.Session, base_url: str, path: Path) -> str:
    with path.open("rb") as fh:
        response = retry_post(
            session,
            f"{base_url}/core-api/admin/app-json/upload-image",
            files={"file": (path.name, fh, "image/jpeg")},
            timeout=120,
            verify=False,
        )
    response.raise_for_status()
    data = response.json()
    payload = data.get("payload")
    item = payload[0] if isinstance(payload, list) else payload
    uri = str(item.get("uri") or "")
    if uri.startswith("/content/"):
        uri = uri.replace("/content/", "/", 1)
    if uri.startswith("/"):
        uri = f"{base_url}{uri}"
    if not uri:
        raise RuntimeError(f"Upload response without uri: {data}")
    return uri


def figure(url: str, caption: str) -> str:
    safe_url = html.escape(url)
    safe_caption = html.escape(caption)
    return (
        '<figure class="content-figure">'
        f'<img src="{safe_url}" alt="{safe_caption}" loading="lazy">'
        f'<figcaption>{safe_caption}</figcaption>'
        "</figure>"
    )


def replace_figures(body: str, first_url: str, second_url: str, title: str) -> str:
    fig_pattern = re.compile(r'<figure class="content-figure">.*?</figure>', flags=re.I | re.S)
    replacements = iter([
        figure(first_url, title),
        figure(second_url, f"{title}: фото з відкритого каталогу Openverse"),
    ])
    if fig_pattern.search(body):
        body = fig_pattern.sub(lambda match: next(replacements, match.group(0)), body, count=2)
    else:
        body = figure(first_url, title) + "\n" + figure(second_url, title) + "\n" + body
    return body


def main() -> int:
    env = load_env()
    base_url = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-openverse-blog/1.0"
    session.post(
        f"{base_url}/core-api/admin/security/login",
        json={"login": env["HOROSHOP_LOGIN"], "password": env["HOROSHOP_PASS"]},
        timeout=60,
        verify=False,
    ).raise_for_status()

    records = active_blog_records(session, base_url)
    records.sort(key=lambda row: int(row["id"]))
    needed = len(records) * 2
    candidates = collect_candidates(records, needed * 2)
    prepared = prepare_images(candidates, needed)
    if len(prepared) < needed:
        raise RuntimeError(f"Only prepared {len(prepared)} images, need {needed}")

    uploaded_urls: list[str] = []
    for item in prepared:
        uploaded_urls.append(upload_editor_image(session, base_url, Path(str(item["local_path"]))))
        time.sleep(0.1)

    updated = []
    for index, record in enumerate(records):
        first_path = Path(str(prepared[index * 2]["local_path"]))
        first_url = uploaded_urls[index * 2]
        second_url = uploaded_urls[index * 2 + 1]
        edit_url = f"{base_url}/adminLegacy/edit.php?id={record['id']}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
        response = retry_get(session, edit_url, timeout=60, verify=False)
        response.raise_for_status()
        payload = parse_form_payload(response.text)
        body = payload.get("names[i18n][3][text]", "")
        new_body = replace_figures(body, first_url, second_url, record["title"])
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
        files = {"names[img][file]": (first_path.name, first_path.open("rb"), "image/jpeg")}
        try:
            save = retry_post(
                session,
                f"{base_url}/adminLegacy/save.php",
                data=payload,
                files=files,
                headers={"Referer": edit_url},
                timeout=120,
                verify=False,
                allow_redirects=True,
            )
        finally:
            files["names[img][file]"][1].close()
        save.raise_for_status()
        updated.append(
            {
                "id": record["id"],
                "title": record["title"],
                "preview_source": prepared[index * 2],
                "body_source": prepared[index * 2 + 1],
                "preview_uploaded": first_url,
                "body_uploaded": second_url,
                "status": save.status_code,
            }
        )
        time.sleep(0.2)

    # Final duplicate audit.
    final_records = active_blog_records(session, base_url)
    body_counts: dict[str, int] = {}
    preview_counts: dict[str, int] = {}
    no_photo = 0
    for record in final_records:
        edit_url = f"{base_url}/adminLegacy/edit.php?id={record['id']}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
        response = retry_get(session, edit_url, timeout=60, verify=False)
        payload = parse_form_payload(response.text)
        preview = payload.get("names[img][value]", "")
        if not preview:
            no_photo += 1
        preview_counts[preview] = preview_counts.get(preview, 0) + 1
        for src in re.findall(r'<img[^>]+src=["\']([^"\']+)', payload.get("names[i18n][3][text]", ""), flags=re.I):
            body_counts[src] = body_counts.get(src, 0) + 1
    blog = retry_get(session, f"{base_url}/blog/?openverse_final=1", timeout=60, verify=False)
    report = {
        "active_count": len(final_records),
        "updated_count": len(updated),
        "candidate_count": len(candidates),
        "prepared_count": len(prepared),
        "updated": updated,
        "duplicate_previews": {url: count for url, count in preview_counts.items() if url and count > 1},
        "duplicate_body_images": {url: count for url, count in body_counts.items() if count > 1},
        "body_image_total": sum(body_counts.values()),
        "body_image_unique": len(body_counts),
        "missing_preview_count": no_photo,
        "blog_noPhoto": blog.text.count("noPhoto"),
        "blog_camera": blog.text.count("camera"),
        "source_policy": {
            "provider": "Openverse API",
            "license_filter": "cc0,pdm",
            "docs": "https://docs.openverse.org/api/",
        },
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "active_count": report["active_count"],
        "updated_count": report["updated_count"],
        "prepared_count": report["prepared_count"],
        "duplicate_previews": report["duplicate_previews"],
        "duplicate_body_images": report["duplicate_body_images"],
        "missing_preview_count": report["missing_preview_count"],
        "blog_noPhoto": report["blog_noPhoto"],
        "blog_camera": report["blog_camera"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
