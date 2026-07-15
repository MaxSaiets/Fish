from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import requests
import urllib3

sys.path.insert(0, str(Path(__file__).resolve().parent))

from enrich_horoshop_site_content import generic_article, save_blog_post, visible_text_and_images
from fill_horoshop_content_pages import load_env, parse_form_payload


urllib3.disable_warnings()

ROOT = Path(r"D:\FISH\fish-sync")
REPORT = ROOT / "data" / "horoshop_blog_extension_report_20260601.json"


MORE_TOPICS = [
    (
        "katushky",
        "Котушка для спінінга, фідера і коропа: як не переплутати розмір",
        "котушка, спінінгова котушка, фідерна котушка, коропова котушка",
        "Пояснюємо розмір котушки, шпулю, фрикціон, передатне число і баланс зі снастю.",
    ),
    (
        "fider-kormushky",
        "Годівниці для фідера: вага, форма, клітка, метод і течія",
        "годівниці, фідер, method feeder, течія, прикормка",
        "Як вибрати годівницю під дистанцію, течію, прикормку і тип дна.",
    ),
    (
        "koropovi-montazhi",
        "Коропові монтажі: безпечна кліпса, лідкор, повідець і гачок",
        "короповий монтаж, безпечна кліпса, лідкор, повідець, гачок",
        "Розбираємо базову логіку коропового монтажу без зайвого ускладнення.",
    ),
    (
        "poplavok",
        "Поплавкова ловля: вудилище, поплавок, грузила і поводок",
        "поплавкова ловля, поплавок, махове вудилище, поводок",
        "Що потрібно для спокійної поплавкової риболовлі на карася, плотву і ляща.",
    ),
    (
        "makhovi-vudylyshcha",
        "Махові вудилища: коли вони кращі за болонські та фідерні",
        "махове вудилище, поплавок, карась, берегова риболовля",
        "Для яких умов підходить махове вудилище і як підібрати довжину.",
    ),
    (
        "bolonski-vudylyshcha",
        "Болонське вудилище: ловля на течії, проводка і контроль снасті",
        "болонське вудилище, течія, поплавкова ловля, проводка",
        "Коли потрібна болонська снасть і чим вона відрізняється від махової.",
    ),
    (
        "pidstavky",
        "Підставки, триноги і род-поди: як стабільно розмістити снасті",
        "підставки, триноги, род-под, фідер, коропова ловля",
        "Як вибрати опору для фідера, коропових вудилищ і берегової риболовлі.",
    ),
    (
        "sumky-chokhly",
        "Сумки, чохли і тубуси: як перевозити вудилища без пошкоджень",
        "чохол для вудилищ, тубус, сумка для риболовлі, транспортування",
        "Пояснюємо, як захистити вудилища, котушки, коробки і дрібні снасті в дорозі.",
    ),
    (
        "zimovi-snasti",
        "Мормишки, балансири і жерлиці: базовий набір для зимової риболовлі",
        "мормишки, балансири, жерлиці, зимова риболовля",
        "Як зібрати зимовий комплект і не забути важливі дрібниці для льоду.",
    ),
    (
        "silicon",
        "Силіконові приманки: форма, розмір, колір і джиг-головка",
        "силіконові приманки, джиг, окунь, щука, судак",
        "Як підібрати силікон під хижака, глибину, течію і активність риби.",
    ),
    (
        "vobler",
        "Воблери: плавучість, заглиблення, проводка і вибір під водойму",
        "воблери, мінноу, кренк, щука, окунь, проводка",
        "Практичний розбір воблерів без складної термінології.",
    ),
    (
        "bleshni",
        "Блешні та вертушки: коли метал працює краще за силікон",
        "блешні, вертушки, коливалки, щука, окунь",
        "Коли обрати блешню, як підібрати вагу і чому важлива швидкість проводки.",
    ),
    (
        "aromaty",
        "Дипи, ліквіди і атрактанти: як підсилити насадку без перебору",
        "дипи, ліквіди, атрактанти, насадки, короп, карась",
        "Як працюють ароматизатори і чому більше запаху не завжди краще.",
    ),
    (
        "sezon",
        "Риболовля по сезонах: що міняти у снастях навесні, влітку і восени",
        "сезонна риболовля, весна, літо, осінь, снасті",
        "Як температура води і активність риби впливають на снасті, прикормку і приманки.",
    ),
    (
        "checklist",
        "Чек-лист перед виїздом: що перевірити вдома, щоб не зірвати риболовлю",
        "чек-лист рибалки, підготовка до риболовлі, снасті, спорядження",
        "Повний список речей і перевірок перед виїздом на водойму.",
    ),
    (
        "podarunok",
        "Подарунок рибалці: що купити, якщо не знаєш його снасті",
        "подарунок рибалці, снасті, аксесуари, сертифікат",
        "Безпечні і корисні ідеї подарунків для рибалки без ризику купити несумісну снасть.",
    ),
]


IMAGE_BY_KEY = {
    "katushky": "reel",
    "fider-kormushky": "cat_real_kormushky",
    "koropovi-montazhi": "cat_real_koropovi",
    "poplavok": "cat_real_poplavky",
    "makhovi-vudylyshcha": "cat_real_makhovi",
    "bolonski-vudylyshcha": "cat_real_bolonski",
    "pidstavky": "cat_real_pidstavky_ta_trynohy",
    "sumky-chokhly": "cat_real_chokhly",
    "zimovi-snasti": "winter",
    "silicon": "cat_real_prymanky",
    "vobler": "lure",
    "bleshni": "cat_real_bleshni",
    "aromaty": "cat_real_likvidy_i_atraktanty",
    "sezon": "water",
    "checklist": "camp",
    "podarunok": "home_rods",
}


def render_topic(topic: dict[str, object]) -> dict[str, str]:
    from enrich_horoshop_site_content import ARTICLE_IMAGES, block, img

    image_key = ARTICLE_IMAGES.get(str(topic["key"]), "water")
    parts = [
        f"<h1>{topic['title']}</h1>",
        img(image_key, str(topic["title"])),
        f"<p><strong>{topic['lead']}</strong></p>",
        "<p>Цей матеріал підготовлений для покупців магазину «Все для рибалки», які хочуть швидко зрозуміти логіку вибору і не купувати зайвого. Текст написаний практичною мовою, без складної термінології та випадкових порад.</p>",
    ]
    for section_title, paragraphs, bullets in topic["sections"]:  # type: ignore[index]
        parts.append(block(section_title, paragraphs, bullets))
    parts.extend(
        [
            img("water", "Рибальські умови змінюються, тому снасті підбирають під задачу"),
            block(
                "Міні-перевірка перед замовленням",
                [
                    "Перед покупкою корисно перевірити кілька простих речей. Це займає менше хвилини, але часто рятує від несумісних товарів і зайвих витрат."
                ],
                [
                    "Для якої риби і водойми купується товар.",
                    "Чи підходить він до снастей, які вже є.",
                    "Чи не потрібні додаткові дрібниці: застібки, поводки, стопори, коробка або чохол.",
                    "Чи зрозумілі розмір, вага, довжина, діаметр або інша ключова характеристика.",
                    "Чи варто уточнити сумісність у менеджера перед оплатою.",
                ],
            ),
            f"<p>{topic['closing']}</p>",
            "<p>Якщо потрібно підібрати позицію під конкретну водойму, краще написати або зателефонувати до магазину. Так можна швидше знайти робочий варіант і не збирати випадковий набір снастей.</p>",
        ]
    )
    return {
        "title": str(topic["title"]),
        "keywords": str(topic["keywords"]),
        "announce": str(topic["announce"]),
        "text": "\n".join(parts).replace(chr(8212), "-").replace(chr(8211), "-"),
    }


def build_posts() -> list[dict[str, str]]:
    from enrich_horoshop_site_content import ARTICLE_IMAGES

    ARTICLE_IMAGES.update(IMAGE_BY_KEY)
    return [render_topic(generic_article(*topic)) for topic in MORE_TOPICS]


def title_ids(session: requests.Session, base_url: str) -> dict[str, str]:
    response = session.get(f"{base_url}/adminLegacy/data.php?parent=1001&handler=172&showPages", timeout=60, verify=False)
    response.raise_for_status()
    mapping: dict[str, str] = {}
    for match in re.finditer(r"id=(\d+)&action=edit&handler=172.*?<a href='#'>(.*?)</a>", response.text, re.S):
        title = re.sub(r"\s+", " ", match.group(2)).strip()
        if title:
            mapping[title] = match.group(1)
    return mapping


def inspect_active(session: requests.Session, base_url: str, start_id: int = 37, end_id: int = 110) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for record_id in range(start_id, end_id + 1):
        edit_url = f"{base_url}/adminLegacy/edit.php?id={record_id}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
        response = session.get(edit_url, timeout=60, verify=False)
        if response.status_code != 200 or "h_news" not in response.text:
            continue
        payload = parse_form_payload(response.text)
        title = payload.get("names[i18n][3][title]", "")
        if not title:
            continue
        body = payload.get("names[i18n][3][text]", "")
        rows.append(
            {
                "id": record_id,
                "act": payload.get("names[act]"),
                "title": title,
                "slug": payload.get("names[name][slug]"),
                "chars": len(body),
                "images": len(re.findall(r"<img\b", body, re.I)),
            }
        )
    return rows


def main() -> int:
    env = load_env()
    base_url = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-blog-extension/1.0"
    session.post(
        f"{base_url}/core-api/admin/security/login",
        json={"login": env["HOROSHOP_LOGIN"], "password": env["HOROSHOP_PASS"]},
        timeout=60,
        verify=False,
    ).raise_for_status()

    existing = title_ids(session, base_url)
    posts = build_posts()
    saved = []
    today = date.today()
    for offset, post in enumerate(posts, start=30):
        saved.append(save_blog_post(session, base_url, post, today - timedelta(days=offset), existing.get(post["title"])))

    active = [row for row in inspect_active(session, base_url) if row.get("act") == "1"]
    public_checks = []
    for row in active:
        slug = str(row.get("slug") or "").strip("/")
        if not slug:
            public_checks.append({"id": row["id"], "slug": slug, "status": "missing_slug"})
            continue
        response = session.get(f"{base_url}/{slug}/?codex_more_blog_verify=1", timeout=60, verify=False)
        text, image_count = visible_text_and_images(response.text)
        public_checks.append(
            {
                "id": row["id"],
                "slug": slug,
                "status": response.status_code,
                "has_title": str(row["title"]) in text,
                "text_chars": len(text),
                "image_count": image_count,
            }
        )

    report = {
        "saved": saved,
        "active_count": len(active),
        "active_records": active,
        "public_checks": public_checks,
        "bad_public_checks": [
            item for item in public_checks
            if item.get("status") != 200 or not item.get("has_title") or int(item.get("image_count") or 0) < 1
        ],
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"saved_count": len(saved), "active_count": len(active), "bad": report["bad_public_checks"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
