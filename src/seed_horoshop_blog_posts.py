from __future__ import annotations

import html
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests
import urllib3

from fill_horoshop_content_pages import FormParser, load_env


urllib3.disable_warnings()

ROOT = Path(r"D:\FISH\fish-sync")
REPORT = ROOT / "data" / "horoshop_blog_seed_report.json"


POSTS: list[dict[str, str]] = [
    {
        "title": "Як вибрати перший спінінг для річки та озера",
        "keywords": "спінінг, вибір спінінга, риболовля на щуку, риболовля на окуня",
        "announce": "Коротко про довжину, тест і стрій спінінга для початку без зайвих витрат.",
        "text": """
<p>Перший спінінг краще обирати не за принципом «найдорожчий», а під водойму і приманки, якими ви реально будете ловити. Для малих річок зручні коротші моделі, для озер і берегових дальніх закидів — довші.</p>
<h2>На що дивитися</h2>
<ul><li>Довжина: 2,1-2,4 м для універсального берега.</li><li>Тест: під вагу приманок, які плануєте використовувати.</li><li>Стрій: fast або medium-fast для більшості задач.</li></ul>
<p>Якщо ловите окуня, щуку або судака різними приманками, краще взяти універсальний комплект і вже потім докуповувати спеціалізовані снасті.</p>
""",
    },
    {
        "title": "Фідер для початківця: що потрібно для першої риболовлі",
        "keywords": "фідер, фідерна ловля, годівниці, прикормка",
        "announce": "Базовий набір для фідерної риболовлі: вудилище, котушка, шнур, годівниці та прикормка.",
        "text": """
<p>Фідерна ловля добре підходить для річок, ставків і водосховищ. Головне — правильно поєднати вудилище, годівницю та прикормку.</p>
<h2>Мінімальний набір</h2>
<ul><li>Фідерне вудилище під дистанцію і течію.</li><li>Котушка з рівною укладкою шнура.</li><li>Годівниці різної ваги.</li><li>Гачки, повідковий матеріал і стопори.</li></ul>
<p>Не варто одразу купувати багато монтажів. Почніть з простого інлайну або патерностера, а потім підбирайте оснащення під умови водойми.</p>
""",
    },
    {
        "title": "Коропова риболовля: базове оснащення без зайвого",
        "keywords": "короп, коропове вудилище, бойли, пелетс, короповий монтаж",
        "announce": "Що потрібно для старту в короповій ловлі і на чому не варто економити.",
        "text": """
<p>У короповій риболовлі важлива системність: міцне вудилище, надійна котушка, безпечний монтаж і правильно підібрана насадка.</p>
<h2>Що взяти на старт</h2>
<ul><li>Коропове вудилище під дистанцію закиду.</li><li>Котушка з фрикціоном або baitrunner.</li><li>Бойли, pop-up, пелетс і прикормка.</li><li>Гачки, лідкор, вертлюги, стопори.</li></ul>
<p>Краще мати менше позицій, але якісних і зрозумілих. Так легше аналізувати, що саме спрацювало на водоймі.</p>
""",
    },
    {
        "title": "Як підібрати прикормку під карася, ляща і коропа",
        "keywords": "прикормка, карась, лящ, короп, рибальська прикормка",
        "announce": "Пояснюємо, як аромат, фракція і липкість прикормки впливають на результат.",
        "text": """
<p>Прикормка має не просто пахнути, а працювати у воді. Для стоячої водойми потрібна одна механіка, для течії — інша.</p>
<h2>Основні параметри</h2>
<ul><li>Фракція: дрібна для обережної риби, крупніша для коропа.</li><li>Липкість: залежить від течії та типу годівниці.</li><li>Аромат: краще підбирати під сезон і температуру води.</li></ul>
<p>Навесні часто краще працюють делікатні аромати, влітку можна пробувати солодкі та фруктові, восени — більш поживні суміші.</p>
""",
    },
    {
        "title": "Пелетс, бойли і pop-up: у чому різниця",
        "keywords": "пелетс, бойли, pop-up, насадки для коропа",
        "announce": "Розбираємо, коли використовувати пелетс, варені бойли та плаваючі pop-up.",
        "text": """
<p>Пелетс, бойли і pop-up часто використовують разом, але задачі в них різні. Пелетс створює кормову пляму, бойл тримає велику рибу, а pop-up піднімає насадку над дном.</p>
<h2>Коли що краще</h2>
<ul><li>Пелетс — для прикормлювання і method feeder.</li><li>Бойли — для селекції більшої риби.</li><li>Pop-up — для мулу, трави або помітної презентації.</li></ul>
<p>Комбінації варто тестувати на конкретній водоймі, бо один і той самий аромат може працювати по-різному.</p>
""",
    },
    {
        "title": "Гачки для риболовлі: як не помилитися з формою і розміром",
        "keywords": "гачки, коропові гачки, спінінгові гачки, офсетні гачки",
        "announce": "Форма, розмір, товщина дроту і гострота — головні критерії вибору гачка.",
        "text": """
<p>Гачок має відповідати насадці, рибі та способу ловлі. Занадто великий гачок насторожує рибу, занадто малий може розігнутися або погано засікати.</p>
<h2>Що врахувати</h2>
<ul><li>Тип ловлі: фідер, короп, спінінг, поплавок.</li><li>Розмір насадки або приманки.</li><li>Товщина дроту і форма жала.</li></ul>
<p>Перед риболовлею перевіряйте гостроту. Тупий гачок може зіпсувати навіть правильно підібрану снасть.</p>
""",
    },
    {
        "title": "Волосінь чи шнур: що краще для ваших умов",
        "keywords": "волосінь, шнур, флюорокарбон, рибальська жилка",
        "announce": "Порівнюємо монофільну волосінь, плетений шнур і флюорокарбон.",
        "text": """
<p>Волосінь краще амортизує ривки риби, шнур дає чутливість, а флюорокарбон менш помітний у воді. Немає одного варіанта для всіх умов.</p>
<h2>Коротке порівняння</h2>
<ul><li>Монофіл — універсальний і пробачає помилки.</li><li>Шнур — чутливий і тонкий при високій міцності.</li><li>Флюорокарбон — добрий для повідців і обережної риби.</li></ul>
<p>Для спінінга часто обирають шнур, для поплавка — волосінь, для повідців — флюорокарбон або спеціальний повідковий матеріал.</p>
""",
    },
    {
        "title": "PVA матеріали: коли вони реально потрібні",
        "keywords": "PVA, pva пакети, pva сітка, коропова ловля",
        "announce": "PVA допомагає точно подати прикормку біля насадки, але має свої нюанси.",
        "text": """
<p>PVA-матеріали розчиняються у воді та дозволяють доставити кормову суміш прямо до насадки. Це особливо корисно на короповій риболовлі.</p>
<h2>Де використовувати</h2>
<ul><li>PVA-пакети — для компактної подачі суміші.</li><li>PVA-сітка — для стіків з дрібним кормом.</li><li>PVA-стрічка — для фіксації монтажу.</li></ul>
<p>Важливо, щоб суміш не була занадто вологою, інакше PVA почне розчинятися раніше часу.</p>
""",
    },
    {
        "title": "Зимова риболовля: що підготувати перед виходом на лід",
        "keywords": "зимова риболовля, мормишки, жерлиці, льодобур",
        "announce": "Снасть, безпека і дрібниці, які вирішують комфорт на зимовій риболовлі.",
        "text": """
<p>Зимова риболовля потребує не тільки снастей, а й уваги до безпеки. Перед виходом на лід перевіряйте товщину льоду та не рибальте наодинці в сумнівних місцях.</p>
<h2>Що взяти</h2>
<ul><li>Зимове вудилище, мормишки або жерлиці.</li><li>Льодобур, черпак, мотильницю.</li><li>Теплий одяг, рукавиці, термос.</li><li>Льодоступи та засоби безпеки.</li></ul>
<p>Краще зібрати комплект заздалегідь, щоб на водоймі не шукати дрібниці в мороз.</p>
""",
    },
    {
        "title": "Як доглядати за котушкою після риболовлі",
        "keywords": "котушка, догляд за котушкою, рибальська котушка",
        "announce": "Прості дії після риболовлі продовжують життя котушки і зберігають плавний хід.",
        "text": """
<p>Котушка працює в пилу, піску, вологи та під навантаженням. Після риболовлі її варто протерти, просушити і перевірити ролик жилковкладача.</p>
<h2>Базовий догляд</h2>
<ul><li>Не мийте котушку сильним струменем води.</li><li>Протирайте корпус вологою серветкою.</li><li>Періодично перевіряйте шнур або волосінь.</li><li>Сервісне обслуговування робіть за потреби.</li></ul>
<p>Якщо з'явився хрускіт, люфт або різке погіршення ходу, краще не затягувати з діагностикою.</p>
""",
    },
    {
        "title": "Органайзери, коробки та сумки: порядок у снастях",
        "keywords": "органайзер, коробка для снастей, сумка для риболовлі",
        "announce": "Правильне зберігання економить час на водоймі та захищає снасті.",
        "text": """
<p>Коли гачки, вертлюги, приманки і поводки лежать окремо, риболовля стає спокійнішою. Органайзер допомагає швидко знайти потрібну дрібницю.</p>
<h2>Як розкласти снасті</h2>
<ul><li>Гачки та дрібну фурнітуру — у коробки з комірками.</li><li>Приманки — за типом і розміром.</li><li>Прикормку і насадки — окремо від одягу та електроніки.</li></ul>
<p>Для регулярних виїздів зручно мати одну основну сумку і кілька невеликих коробок під конкретний тип ловлі.</p>
""",
    },
    {
        "title": "Самовивіз чи доставка: як швидше отримати замовлення",
        "keywords": "доставка рибальських товарів, самовивіз Хмельницький, Нова пошта, Укрпошта",
        "announce": "Пояснюємо, коли краще обрати самовивіз, а коли доставку перевізником.",
        "text": """
<p>Якщо ви у Хмельницькому, самовивіз дозволяє швидко забрати товар і на місці уточнити деталі. Для інших міст зручна доставка Новою поштою або Укрпоштою.</p>
<h2>Що врахувати</h2>
<ul><li>Габарити вудилищ і тубусів.</li><li>Вагу прикормки, пелетсу та аксесуарів.</li><li>Терміновість замовлення.</li></ul>
<p>Перед відправкою ми перевіряємо наявність і узгоджуємо деталі, щоб посилка приїхала саме в потрібній комплектації.</p>
""",
    },
]


def parse_payload(form_html: str) -> dict[str, Any]:
    parser = FormParser()
    parser.feed(form_html)
    return parser.payload


def slugify(text: str) -> str:
    mapping = {
        "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d", "е": "e", "є": "ie", "ж": "zh", "з": "z",
        "и": "y", "і": "i", "ї": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p",
        "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh",
        "щ": "shch", "ь": "", "ю": "iu", "я": "ia",
    }
    raw = "".join(mapping.get(ch, ch) for ch in text.lower())
    raw = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return raw[:90]


def resolve_horoshop_slug(session: requests.Session, base_url: str, title: str, record_id: str = "0") -> tuple[str, str]:
    response = session.post(
        f"{base_url}/_widget/zteel_params_url_Param/updateUriAutomatically",
        data={
            "fields[title]": title,
            "param_id": "3520",
            "record_id": record_id,
            "parent_id": "1001",
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
        timeout=60,
        verify=False,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("status") == "OK":
        payload = data.get("response") or {}
        return str(payload.get("slug") or slugify(title)), str(payload.get("parent") or "151")
    return slugify(title), "151"


def post_exists(session: requests.Session, base_url: str, slug: str) -> bool:
    response = session.get(f"{base_url}/{slug}/", timeout=60)
    return response.status_code == 200 and "Сторінку не знайдено" not in response.text


def save_post(session: requests.Session, base_url: str, post: dict[str, str], post_date: date) -> dict[str, str]:
    slug, url_parent = resolve_horoshop_slug(session, base_url, post["title"])
    if post_exists(session, base_url, slug):
        return {"title": post["title"], "slug": slug, "status": "skipped_exists"}

    edit_url = f"{base_url}/adminLegacy/edit.php?id=addnew&parent=1001&handler=172&checkcode=yamete_kudasai&showPages"
    response = session.get(edit_url, timeout=60, verify=False)
    response.raise_for_status()
    payload = parse_payload(response.text)
    payload.update(
        {
            "checkcode": "yamete_kudasai",
            "id": "addnew",
            "handler": "172",
            "handlertable": "h_news",
            "back": "index.php",
            "names[act]": "1",
            "names[parent]": "1001",
            "names[date]": post_date.isoformat(),
            "names[name][slug]": slug,
            "names[name][parent]": url_parent,
            "names[i18n][3][title]": post["title"],
            "names[i18n][3][announce]": post["announce"],
            "names[i18n][3][text]": post["text"].strip(),
            "names[i18n][3][h1_title]": post["title"],
            "names[i18n][3][seo_title]": f"{post['title']} — поради від Все для рибалки",
            "names[i18n][3][seo_keywords]": post["keywords"],
            "names[i18n][3][seo_description]": post["announce"],
            "names[promo]": "0",
            "names[disallow_comments]": "0",
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
    return {"title": post["title"], "slug": slug, "status": str(save.status_code), "final_url": save.url}


def title_to_ids(session: requests.Session, base_url: str) -> dict[str, str]:
    response = session.get(f"{base_url}/adminLegacy/data.php?parent=1001&handler=172&showPages", timeout=60, verify=False)
    response.raise_for_status()
    mapping: dict[str, str] = {}
    for match in re.finditer(r"id=(\d+)&action=edit&handler=172[^>]+><a href='#'>(.*?)</a>", response.text):
        mapping[html.unescape(match.group(2))] = match.group(1)
    return mapping


def ensure_post_urls(session: requests.Session, base_url: str, results: list[dict[str, str]]) -> list[dict[str, str]]:
    ids = title_to_ids(session, base_url)
    fixed: list[dict[str, str]] = []
    for item in results:
        record_id = ids.get(item["title"])
        if not record_id:
            fixed.append({**item, "url_fix": "id_not_found"})
            continue
        edit_url = f"{base_url}/adminLegacy/edit.php?id={record_id}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
        response = session.get(edit_url, timeout=60, verify=False)
        response.raise_for_status()
        payload = parse_payload(response.text)
        slug, url_parent = resolve_horoshop_slug(session, base_url, item["title"], record_id)
        payload.update(
            {
                "checkcode": "yamete_kudasai",
                "id": record_id,
                "handler": "172",
                "handlertable": "h_news",
                "back": "index.php",
                "names[act]": "1",
                "names[parent]": "1001",
                "names[name][slug]": slug,
                "names[name][parent]": url_parent,
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
        fixed.append({**item, "id": record_id, "slug": slug, "url_fix": str(save.status_code)})
    return fixed


def main() -> int:
    env = load_env()
    base_url = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-blog-seed/1.0"
    auth = session.post(
        f"{base_url}/core-api/admin/security/login",
        json={"login": env["HOROSHOP_LOGIN"], "password": env["HOROSHOP_PASS"]},
        timeout=60,
        verify=False,
    )
    auth.raise_for_status()

    today = date.today()
    results = [save_post(session, base_url, post, today - timedelta(days=i)) for i, post in enumerate(POSTS)]
    results = ensure_post_urls(session, base_url, results)
    verification = {}
    for item in results:
        if item["status"] == "skipped_exists":
            continue
        response = session.get(f"{base_url}/{item['slug']}/?codex_blog_verify=1", timeout=60)
        verification[item["slug"]] = {
            "status_code": response.status_code,
            "has_title": item["title"] in html.unescape(response.text),
        }
    report = {"base_url": base_url, "created_or_checked": results, "verification": verification}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
