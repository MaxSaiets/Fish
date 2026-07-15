from __future__ import annotations

import html
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests
import urllib3

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fill_horoshop_content_pages import load_env, parse_form_payload
from seed_horoshop_blog_posts import resolve_horoshop_slug, slugify
from upgrade_horoshop_blog_full import TOPICS, figure, render_article, visible_text_and_images


urllib3.disable_warnings()

ROOT = Path(r"D:\FISH\fish-sync")
VISUALS_REPORT = ROOT / "data" / "horoshop_category_visuals_report.json"
REPORT = ROOT / "data" / "horoshop_blog_final_repair_report_20260601.json"


def visuals() -> dict[str, dict[str, Any]]:
    data = json.loads(VISUALS_REPORT.read_text(encoding="utf-8"))
    return data.get("uploads", {})


VISUALS = visuals()


def local_image_path(key: str) -> Path:
    item = VISUALS.get(key) or VISUALS.get("water") or {}
    path = Path(item.get("local_path") or "")
    if path.exists():
        return path
    raise FileNotFoundError(f"No local image for {key}: {path}")


def inspect_records(session: requests.Session, base_url: str, max_id: int = 180) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for record_id in range(1, max_id + 1):
        edit_url = f"{base_url}/adminLegacy/edit.php?id={record_id}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
        response = session.get(edit_url, timeout=60, verify=False)
        if response.status_code != 200 or "h_news" not in response.text:
            continue
        payload = parse_form_payload(response.text)
        title = payload.get("names[i18n][3][title]", "")
        if not title:
            continue
        body = payload.get("names[i18n][3][text]", "")
        records.append(
            {
                "id": record_id,
                "title": title,
                "act": payload.get("names[act]"),
                "slug": payload.get("names[name][slug]") or "",
                "img": payload.get("names[img][value]") or "",
                "chars": len(body),
                "ul_count": body.lower().count("<ul"),
            }
        )
    return records


def choose_records(records: list[dict[str, Any]]) -> dict[str, int]:
    chosen: dict[str, int] = {}
    by_title: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_title.setdefault(str(record["title"]), []).append(record)
    for topic in TOPICS:
        title = topic["title"]
        candidates = by_title.get(title, [])
        if not candidates:
            continue
        desired = slugify(title)
        def score(record: dict[str, Any]) -> tuple[int, int, int, int]:
            slug = str(record.get("slug") or "").strip("/")
            return (
                1 if slug == desired else 0,
                1 if slug and "/" not in slug else 0,
                int(record.get("id") or 0),
                int(record.get("chars") or 0),
            )
        chosen[title] = int(max(candidates, key=score)["id"])
    return chosen


def long_article(topic: dict[str, str], index: int) -> str:
    base = render_article(topic, index)
    extra = [
        ("Приклад логіки вибору", f"Уявімо звичайну ситуацію: покупець збирається на водойму, де умови змінюються протягом дня. Зранку риба може стояти ближче до берега, після обіду відійти на глибину, а ввечері знову реагувати на іншу подачу. Саме тому {topic['kind']} варто підбирати так, щоб залишався запас для маневру, але без втрати контролю. Якщо рішення занадто грубе, воно прибирає чутливість. Якщо занадто делікатне, воно може не витримати навантаження або перестати працювати у складніших умовах."),
        ("Що часто недооцінюють", f"Багато рибалок звертають увагу на головний товар, але забувають про оточення. Для {topic['kind']} важливо, як він взаємодіє з рештою комплекту. Снасть має працювати як одна система, а не як набір випадкових покупок. Навіть невелика різниця у вазі, довжині, діаметрі чи формі може змінити поведінку снасті на закиді, у воді та під час виведення."),
        ("Як зрозуміти, що вибір вдалий", "Вдалий вибір відчувається дуже просто: снасть не заважає ловити. Вона не змушує постійно переробляти монтаж, не плутається без причини, не перевантажує руку, не викликає сумнівів перед кожним закидом. Коли комплект підібраний правильно, рибалка більше думає про водойму, точку і поведінку риби, а не про те, чому щось знову працює не так."),
        ("Як купувати без зайвого запасу", "Не потрібно одразу брати все, що може колись знадобитися. Краще купити робочу основу і кілька продуманих доповнень. Після двох або трьох виїздів стане зрозуміло, чого справді бракує. Такий підхід спокійніший для бюджету і корисніший для досвіду, бо кожна покупка має причину."),
        ("Порада перед замовленням", "Якщо картка товару здається зрозумілою, але є сумнів у сумісності, краще уточнити деталь до оформлення. Це особливо важливо для товарів, де схожі назви приховують різні характеристики. У риболовлі дрібна різниця часто стає великою вже на березі."),
    ]
    insertion = []
    for heading, paragraph in extra:
        insertion.append(f"<h2>{html.escape(heading)}</h2>")
        insertion.append(f"<p>{html.escape(paragraph)}</p>")
    return (base + "\n" + "\n".join(insertion)).replace(chr(8212), "-").replace(chr(8211), "-")


def save_topic(
    session: requests.Session,
    base_url: str,
    topic: dict[str, str],
    index: int,
    record_id: int | None,
) -> dict[str, Any]:
    edit_url = (
        f"{base_url}/adminLegacy/edit.php?id={record_id}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
        if record_id
        else f"{base_url}/adminLegacy/edit.php?id=addnew&parent=1001&handler=172&checkcode=yamete_kudasai&showPages"
    )
    response = session.get(edit_url, timeout=60, verify=False)
    response.raise_for_status()
    payload = parse_form_payload(response.text)
    slug, url_parent = resolve_horoshop_slug(session, base_url, topic["title"], str(record_id or "0"))
    slug = slug.replace("/{id}", "").replace("{id}", "").strip("/") or slugify(topic["title"])
    body = long_article(topic, index)
    article_date = date(2026, 5, 31) - timedelta(days=index * 4 + (index % 5))
    announce = f"Докладна стаття про {topic['kind']}: як вибирати під реальні умови, на що дивитися в характеристиках і як не купити зайве."
    payload.update(
        {
            "checkcode": "yamete_kudasai",
            "id": str(record_id or "addnew"),
            "handler": "172",
            "handlertable": "h_news",
            "back": "index.php",
            "names[act]": "1",
            "names[parent]": "1001",
            "names[date]": article_date.isoformat(),
            "names[name][slug]": slug,
            "names[name][parent]": url_parent,
            "names[i18n][3][title]": topic["title"],
            "names[i18n][3][announce]": announce,
            "names[i18n][3][text]": body,
            "names[i18n][3][h1_title]": topic["title"],
            "names[i18n][3][seo_title]": f"{topic['title']} | Все для рибалки",
            "names[i18n][3][seo_keywords]": f"{topic['kind']}, риболовля, снасті, магазин все для рибалки",
            "names[i18n][3][seo_description]": announce,
            "names[promo]": "0",
            "names[disallow_comments]": "0",
        }
    )
    image_path = local_image_path(topic["key"])
    files = {
        "names[img][file]": (image_path.name, image_path.open("rb"), "image/jpeg"),
    }
    try:
        save = session.post(
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
    return {
        "title": topic["title"],
        "id": record_id or "",
        "slug": slug,
        "date": article_date.isoformat(),
        "image_key": topic["key"],
        "chars": len(body),
        "ul_count": body.lower().count("<ul"),
        "status": save.status_code,
    }


def deactivate(session: requests.Session, base_url: str, record_id: int) -> dict[str, Any]:
    edit_url = f"{base_url}/adminLegacy/edit.php?id={record_id}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
    response = session.get(edit_url, timeout=60, verify=False)
    response.raise_for_status()
    payload = parse_form_payload(response.text)
    payload.update(
        {
            "checkcode": "yamete_kudasai",
            "id": str(record_id),
            "handler": "172",
            "handlertable": "h_news",
            "back": "index.php",
            "names[act]": "0",
            "names[parent]": "1001",
        }
    )
    save = session.post(
        f"{base_url}/adminLegacy/save.php",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": edit_url},
        timeout=60,
        verify=False,
        allow_redirects=True,
    )
    save.raise_for_status()
    return {"id": record_id, "title": payload.get("names[i18n][3][title]", ""), "status": save.status_code}


def main() -> int:
    env = load_env()
    base_url = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-blog-final-repair/1.0"
    session.post(
        f"{base_url}/core-api/admin/security/login",
        json={"login": env["HOROSHOP_LOGIN"], "password": env["HOROSHOP_PASS"]},
        timeout=60,
        verify=False,
    ).raise_for_status()

    before = inspect_records(session, base_url)
    chosen = choose_records(before)
    saved = []
    for index, topic in enumerate(TOPICS):
        saved.append(save_topic(session, base_url, topic, index, chosen.get(topic["title"])))

    after_save = inspect_records(session, base_url)
    keep_ids = {int(item["id"]) for item in saved if item.get("id")}
    deactivated = []
    for record in after_save:
        if record.get("act") == "1" and int(record["id"]) not in keep_ids:
            deactivated.append(deactivate(session, base_url, int(record["id"])))

    final_records = inspect_records(session, base_url)
    active = [record for record in final_records if record.get("act") == "1"]
    public_checks = []
    for record in active:
        slug = str(record.get("slug") or "").strip("/")
        response = session.get(f"{base_url}/{slug}/?codex_final_blog_repair=1", timeout=60, verify=False)
        text, image_count = visible_text_and_images(response.text)
        public_checks.append(
            {
                "id": record["id"],
                "slug": slug,
                "status": response.status_code,
                "has_title": str(record["title"]) in text,
                "text_chars": len(text),
                "image_count": image_count,
                "preview_img": record.get("img"),
                "body_chars": record.get("chars"),
                "ul_count": record.get("ul_count"),
            }
        )
    blog = session.get(f"{base_url}/blog/?codex_final_preview_check=1", timeout=60, verify=False)
    report = {
        "saved_count": len(saved),
        "saved": saved,
        "deactivated_count": len(deactivated),
        "deactivated": deactivated,
        "active_count": len(active),
        "active_records": active,
        "unique_preview_images": len({record.get("img") for record in active if record.get("img")}),
        "public_checks": public_checks,
        "bad": [
            item for item in public_checks
            if item["status"] != 200
            or not item["has_title"]
            or not item.get("preview_img")
            or int(item.get("body_chars") or 0) < 7600
            or int(item.get("ul_count") or 0) > 0
        ],
        "blog_list_status": blog.status_code,
        "blog_list_no_photo_count": blog.text.count("noPhoto"),
        "blog_list_camera_count": blog.text.count("camera"),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "saved_count": report["saved_count"],
        "deactivated_count": report["deactivated_count"],
        "active_count": report["active_count"],
        "unique_preview_images": report["unique_preview_images"],
        "blog_list_no_photo_count": report["blog_list_no_photo_count"],
        "blog_list_camera_count": report["blog_list_camera_count"],
        "bad": report["bad"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
