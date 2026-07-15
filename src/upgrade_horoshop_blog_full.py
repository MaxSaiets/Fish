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

from enrich_horoshop_site_content import visible_text_and_images
from fill_horoshop_content_pages import load_env, parse_form_payload
from seed_horoshop_blog_posts import resolve_horoshop_slug, slugify


urllib3.disable_warnings()

ROOT = Path(r"D:\FISH\fish-sync")
VISUALS_REPORT = ROOT / "data" / "horoshop_category_visuals_report.json"
REPORT = ROOT / "data" / "horoshop_blog_full_upgrade_report_20260601.json"


def image_urls() -> dict[str, str]:
    data = json.loads(VISUALS_REPORT.read_text(encoding="utf-8"))
    return {key: value["uri"] for key, value in data.get("uploads", {}).items() if value.get("uri")}


IMAGES = image_urls()


def public_to_hidden(src: str) -> str:
    return src.replace("https://vsedliarybalky.com.ua/images/", "/content/images/")


def figure(image_key: str, alt: str) -> str:
    src = IMAGES.get(image_key) or IMAGES.get("water") or ""
    if not src:
        return ""
    return (
        '<figure class="content-figure">'
        f'<img src="{html.escape(src)}" alt="{html.escape(alt)}" loading="lazy">'
        f'<figcaption>{html.escape(alt)}</figcaption>'
        "</figure>"
    )


TOPICS: list[dict[str, str]] = [
    {"title": "Як вибрати перший спінінг для річки та озера", "key": "cat_unique_spininhovi", "kind": "спінінг", "fish": "щуку, окуня і судака", "intent": "підібрати перший комплект без зайвих витрат"},
    {"title": "Фідер для початківця: що потрібно для першої риболовлі", "key": "cat_unique_fiderni", "kind": "фідер", "fish": "ляща, карася і плотву", "intent": "зібрати зрозумілий набір для першого виїзду"},
    {"title": "Коропова риболовля: базове оснащення без зайвого", "key": "cat_unique_koropovi", "kind": "коропова ловля", "fish": "коропа і амура", "intent": "побудувати надійну систему з безпечним монтажем"},
    {"title": "Як підібрати прикормку під карася, ляща і коропа", "key": "cat_unique_prykormka", "kind": "прикормка", "fish": "карася, ляща і коропа", "intent": "зрозуміти фракцію, аромат і механіку суміші"},
    {"title": "Пелетс, бойли і pop-up: як скласти робочу програму насадок", "key": "cat_unique_peletsy", "kind": "насадки", "fish": "коропа, амура і великого карася", "intent": "поєднувати насадки без випадкового набору банок"},
    {"title": "Гачки для риболовлі: форма, дріт, жало і правильний розмір", "key": "cat_unique_hachky", "kind": "гачки", "fish": "мирну і хижу рибу", "intent": "підібрати форму і розмір під насадку"},
    {"title": "Волосінь, шнур і флюорокарбон: як вибрати без помилки", "key": "cat_unique_fliuorokarbon", "kind": "основа і повідці", "fish": "обережну і активну рибу", "intent": "не переплутати матеріал під різні задачі"},
    {"title": "PVA матеріали: пакети, сітка, стіки і типові помилки", "key": "cat_unique_pva_materialy", "kind": "PVA", "fish": "коропа", "intent": "точно подати корм біля насадки"},
    {"title": "Зимова риболовля: спорядження, безпека і підготовка до льоду", "key": "winter", "kind": "зимова ловля", "fish": "окуня, плотву і щуку", "intent": "підготувати снасті та не забути про безпеку"},
    {"title": "Як доглядати за котушкою після риболовлі", "key": "reel", "kind": "котушка", "fish": "будь-яку рибу", "intent": "зберегти плавний хід і ресурс механізму"},
    {"title": "Органайзери, коробки та сумки: як навести порядок у снастях", "key": "cat_unique_korobky_orhanaizery", "kind": "зберігання снастей", "fish": "усі види риболовлі", "intent": "швидко знаходити потрібну дрібницю на водоймі"},
    {"title": "Самовивіз чи доставка: як безпечно отримати рибальські товари", "key": "camp", "kind": "доставка", "fish": "будь-який напрям риболовлі", "intent": "отримати замовлення без пошкоджень"},
    {"title": "Воблери, блешні і силікон: як підібрати приманку під хижака", "key": "cat_unique_prymanky", "kind": "приманки", "fish": "щуку, окуня і судака", "intent": "підібрати приманку під глибину і активність риби"},
    {"title": "Монтажі, вертлюги і грузила: дрібниці, які впливають на клювання", "key": "cat_unique_vse_dlia_montazhu", "kind": "монтажі", "fish": "мирну рибу і хижака", "intent": "зробити снасть акуратною і надійною"},
    {"title": "Підсаки, садки і кукани: як зберегти рибу та снасті", "key": "cat_unique_pidsaky", "kind": "підсаки і садки", "fish": "рибу біля берега", "intent": "безпечно взяти трофей і не пошкодити снасті"},
    {"title": "Крісла, столи і туристичне спорядження для довгої риболовлі", "key": "cat_unique_krisla", "kind": "комфорт", "fish": "довгі рибальські виїзди", "intent": "зробити день на водоймі зручним"},
    {"title": "Котушка для спінінга, фідера і коропа: як не переплутати розмір", "key": "cat_unique_kotushky", "kind": "котушка", "fish": "різні стилі ловлі", "intent": "підібрати розмір, шпулю і фрикціон"},
    {"title": "Годівниці для фідера: вага, форма, клітка, метод і течія", "key": "cat_unique_kormushky", "kind": "годівниці", "fish": "ляща, карася і коропа", "intent": "обрати вагу і форму під точку"},
    {"title": "Коропові монтажі: безпечна кліпса, лідкор, повідець і гачок", "key": "cat_unique_koropovi_hachky", "kind": "короповий монтаж", "fish": "коропа", "intent": "зібрати безпечну та міцну оснастку"},
    {"title": "Поплавкова ловля: вудилище, поплавок, грузила і поводок", "key": "cat_unique_poplavky", "kind": "поплавкова ловля", "fish": "карася, плотву і ляща", "intent": "збалансувати легку снасть"},
    {"title": "Махові вудилища: коли вони кращі за болонські та фідерні", "key": "cat_unique_makhovi", "kind": "махове вудилище", "fish": "карася і плотву", "intent": "підібрати довжину під берег"},
    {"title": "Болонське вудилище: ловля на течії, проводка і контроль снасті", "key": "cat_unique_bolonski", "kind": "болонська снасть", "fish": "плотву, головня і ляща", "intent": "контролювати проводку на течії"},
    {"title": "Підставки, триноги і род-поди: як стабільно розмістити снасті", "key": "cat_unique_pidstavky_ta_trynohy", "kind": "підставки", "fish": "фідерну і коропову ловлю", "intent": "надійно поставити вудилища на березі"},
    {"title": "Сумки, чохли і тубуси: як перевозити вудилища без пошкоджень", "key": "cat_unique_chokhly", "kind": "транспортування", "fish": "всі снасті", "intent": "захистити вудилища і котушки дорогою"},
    {"title": "Мормишки, балансири і жерлиці: базовий набір для зимової риболовлі", "key": "cat_unique_mormyshky", "kind": "зимові снасті", "fish": "окуня, щуку і плотву", "intent": "зібрати робочий зимовий набір"},
    {"title": "Силіконові приманки: форма, розмір, колір і джиг-головка", "key": "cat_unique_prymanky", "kind": "силікон", "fish": "окуня, судака і щуку", "intent": "підлаштувати приманку під дно і активність"},
    {"title": "Воблери: плавучість, заглиблення, проводка і вибір під водойму", "key": "lure", "kind": "воблери", "fish": "щуку і окуня", "intent": "зрозуміти заглиблення і гру"},
    {"title": "Блешні та вертушки: коли метал працює краще за силікон", "key": "cat_unique_bleshni", "kind": "блешні", "fish": "активного хижака", "intent": "підібрати вагу і темп проводки"},
    {"title": "Дипи, ліквіди і атрактанти: як підсилити насадку без перебору", "key": "cat_unique_likvidy_i_atraktanty", "kind": "атрактанти", "fish": "коропа, карася і ляща", "intent": "працювати з ароматом обережно"},
    {"title": "Риболовля по сезонах: що міняти у снастях навесні, влітку і восени", "key": "water", "kind": "сезонність", "fish": "різну рибу протягом року", "intent": "підлаштувати снасті під температуру води"},
    {"title": "Чек-лист перед виїздом: що перевірити вдома, щоб не зірвати риболовлю", "key": "home_hero", "kind": "підготовка", "fish": "будь-який виїзд", "intent": "не забути важливі дрібниці"},
    {"title": "Подарунок рибалці: що купити, якщо не знаєш його снасті", "key": "home_rods", "kind": "подарунок", "fish": "рибалку з будь-яким досвідом", "intent": "обрати корисну річ без ризику"},
    {"title": "Флюорокарбон для повідців: коли прозорість справді має значення", "key": "cat_unique_fliuorokarbon", "kind": "флюорокарбон", "fish": "обережну рибу", "intent": "зробити поводок менш помітним"},
    {"title": "Грузила для спінінга, фідера і монтажів: як підібрати вагу", "key": "cat_unique_hruzyla", "kind": "грузила", "fish": "різні умови ловлі", "intent": "не перевантажити снасть"},
    {"title": "Карабіни, вертлюги та кільця: дрібна фурнітура без слабких місць", "key": "cat_unique_karabiny_vertliuhy_ta_kiltsia", "kind": "фурнітура", "fish": "будь-яку снасть", "intent": "уникнути обривів на дрібницях"},
    {"title": "Бойли для коропа: розмір, плавучість, аромат і подача", "key": "cat_unique_boily", "kind": "бойли", "fish": "коропа", "intent": "підібрати насадку під дно і сезон"},
    {"title": "Pop-up насадки: коли плаваюча презентація дає перевагу", "key": "cat_unique_pop_ap", "kind": "pop-up", "fish": "коропа і амура", "intent": "підняти насадку над мулом або травою"},
    {"title": "Макуха і технопланктон: коли класичні насадки ще працюють", "key": "cat_unique_makukha", "kind": "макуха", "fish": "коропа, товстолоба і карася", "intent": "використати прості перевірені рішення"},
    {"title": "Підсаки для берега і човна: форма голови, ручка та сітка", "key": "cat_unique_ruchky_ta_holovy_do_pidsakiv", "kind": "підсак", "fish": "велику рибу", "intent": "взяти рибу без поспіху і втрат"},
    {"title": "Сигналізатори клювання: механічні та електронні варіанти", "key": "cat_unique_syhnalizatory_kliuvannia", "kind": "сигналізатори", "fish": "коропову і донну ловлю", "intent": "не пропустити клювання"},
    {"title": "Ліхтарі, батарейки і нічна риболовля: що підготувати заздалегідь", "key": "cat_unique_likhtari", "kind": "нічне спорядження", "fish": "нічний виїзд", "intent": "бачити снасті і працювати безпечно"},
    {"title": "Садок чи кукан: як зберігати рибу на водоймі", "key": "cat_unique_sadky_kukany", "kind": "зберігання риби", "fish": "улов на водоймі", "intent": "зберегти рибу живою і не травмувати"},
    {"title": "Коробки для приманок: як розділити воблери, силікон і фурнітуру", "key": "cat_unique_korobky_orhanaizery", "kind": "коробки", "fish": "спінінгові приманки", "intent": "прибрати хаос у рюкзаку"},
    {"title": "Крісла для риболовлі: комфорт, вага, ніжки і посадка", "key": "cat_unique_krisla_stiltsi_ta_stoly", "kind": "крісла", "fish": "довгу риболовлю", "intent": "сидіти зручно на різному березі"},
    {"title": "Плити, пальники і посуд: польова кухня на риболовлі", "key": "cat_unique_plyty_horilky_balony", "kind": "польова кухня", "fish": "тривалий виїзд", "intent": "організувати чай, їжу і тепло"},
    {"title": "Запчастини до вудилищ: вершинки, кільця і дрібний ремонт", "key": "cat_unique_zapchastyny_do_vudylyshch", "kind": "ремонт", "fish": "вудилища після навантаження", "intent": "швидко повернути снасть у роботу"},
    {"title": "Повідковий матеріал: м’якість, міцність і поведінка насадки", "key": "cat_unique_povidkovyi_material", "kind": "повідковий матеріал", "fish": "коропа і обережну рибу", "intent": "налаштувати презентацію насадки"},
    {"title": "Метод-фідер: як працює годівниця з плоским дном", "key": "cat_unique_kormushky", "kind": "метод-фідер", "fish": "карася і коропа", "intent": "подати насадку прямо в кормовій плямі"},
    {"title": "Рибальський мінімум для новачка: що купити першим", "key": "cat_unique_nabory", "kind": "перший набір", "fish": "першу риболовлю", "intent": "не переплатити за зайве"},
    {"title": "Як читати характеристики товару і не помилятися в замовленні", "key": "cat_unique_aksesuary", "kind": "характеристики", "fish": "онлайн-покупку", "intent": "зрозуміти ключові параметри в картці товару"},
]


def paragraphs(topic: dict[str, str], index: int) -> list[str]:
    kind = topic["kind"]
    fish = topic["fish"]
    intent = topic["intent"]
    return [
        f"{topic['title']} це тема, яка напряму впливає на результат риболовлі. Покупець часто бачить у каталозі десятки схожих позицій і не одразу розуміє, чим вони відрізняються. Насправді правильний вибір починається не з бренду і не з ціни, а з водойми, умов ловлі, очікуваної риби та того, як саме снасть буде використовуватись протягом дня.",
        f"Якщо говорити про {kind}, важливо не шукати один універсальний варіант для всіх ситуацій. У риболовлі майже кожна деталь має контекст. Те, що добре працює на тихому ставку, може бути незручним на течії. Те, що підходить для короткої дистанції, може програвати на дальньому закиді. Саме тому перед покупкою варто чесно відповісти собі, де ви ловите найчастіше і яку задачу хочете закрити.",
        f"Головна практична мета такого вибору: {intent}. Якщо товар вирішує саме цю задачу, він буде корисним навіть без гучної назви. Якщо задача не визначена, у кошику швидко з'являються випадкові позиції, які потім лежать у коробці і майже не використовуються.",
        f"Для ловлі на {fish} потрібно дивитися не тільки на одну характеристику. Важлива сумісність усієї системи: вудилище, котушка, основа, повідець, монтаж, приманка або насадка, вага, розмір і спосіб подачі. Коли один елемент вибивається з системи, снасть стає менш керованою, навіть якщо кожна окрема покупка здавалась якісною.",
        f"У магазині часто питають, чи варто брати дорожчий варіант одразу. Відповідь залежить від частоти виїздів і вимог до снасті. Якщо ви рибалите кілька разів на сезон, іноді достатньо простого надійного рішення. Якщо ви регулярно їздите на одну й ту саму водойму і вже розумієте слабкі місця комплекту, тоді точніша характеристика справді може дати відчутну перевагу.",
        f"Окрема увага потрібна дрібницям. У риболовлі вони рідко виглядають важливими на фото, але саме вони часто вирішують результат. Неправильний діаметр, слабка застібка, надто грубий гачок, невдала вага або незручне пакування можуть зіпсувати роботу всієї снасті. Тому {kind} краще оцінювати не ізольовано, а як частину повного набору.",
        f"Ще одна типова помилка це копіювати чужий комплект без поправки на свої умови. У знайомого може бути інша водойма, інша дистанція, інший берег, інший темп ловлі та інша риба. Його рішення може бути хорошим, але не обов'язково стане хорошим для вас. Правильніше брати чужий досвід як підказку, а не як готовий рецепт.",
        f"Перед виїздом корисно перевірити снасть вдома. Це простий крок, який економить нерви на березі. Варто подивитися, чи все зібрано, чи немає пошкоджень, чи вистачає витратних матеріалів, чи підходять розміри і чи не забута дрібна фурнітура. Найгірше виявити нестачу тоді, коли риба вже активна, а магазин далеко.",
        f"На водоймі не поспішайте змінювати все одразу. Якщо немає результату, краще міняти один параметр за раз: дистанцію, вагу, насадку, аромат, проводку, розмір або подачу. Так ви зрозумієте, що саме вплинуло на клювання. Коли змінюється все одночасно, досвід не накопичується, і наступного разу доводиться знову вгадувати.",
        f"Для онлайн-замовлення найважливіше уважно читати характеристики. Назва товару може бути схожою, але різниця у довжині, тесті, діаметрі, вазі, плавучості або розмірі змінює призначення. Якщо характеристика незрозуміла, краще уточнити її до покупки. Це нормальна частина підбору, а не ознака недосвідченості.",
        f"Добре підібраний {kind} не обов'язково має бути найдорожчим. Він має бути зрозумілим, сумісним і доречним для вашої риболовлі. Саме такий підхід допомагає поступово зібрати набір, у якому кожна річ використовується, а не просто займає місце.",
        f"Якщо ви сумніваєтесь, опишіть менеджеру водойму, рибу, сезон і снасті, які вже маєте. По цих даних значно легше підібрати робочий варіант. У магазині «Все для рибалки» можна уточнити сумісність перед замовленням і не збирати кошик навмання.",
    ]


def render_article(topic: dict[str, str], index: int) -> str:
    parts = [
        f"<h1>{html.escape(topic['title'])}</h1>",
        figure(topic["key"], topic["title"]),
    ]
    headings = [
        "З чого почати вибір",
        "Як зрозуміти свої умови",
        "Сумісність важливіша за випадкову популярність",
        "Що перевірити перед покупкою",
        "Як тестувати на водоймі",
        "Коли варто звернутися за консультацією",
    ]
    ps = paragraphs(topic, index)
    parts.append(f"<p><strong>{html.escape(ps[0])}</strong></p>")
    for h_idx, heading in enumerate(headings):
        parts.append(f"<h2>{heading}</h2>")
        for paragraph in ps[1 + h_idx * 2: 1 + h_idx * 2 + 2]:
            parts.append(f"<p>{html.escape(paragraph)}</p>")
        if h_idx == 2:
            parts.append(figure("water", "Риболовля потребує підбору снастей під реальні умови"))
    parts.append("<h2>Підсумок</h2>")
    parts.append(
        f"<p>{html.escape('Правильний вибір не має бути складним. Достатньо розуміти задачу, не поспішати з випадковими покупками і перевіряти сумісність деталей. Тоді кожна наступна риболовля стає передбачуванішою, а набір снастей поступово перетворюється на робочу систему.')}</p>"
    )
    return "\n".join(parts).replace(chr(8212), "-").replace(chr(8211), "-")


def title_ids(session: requests.Session, base_url: str) -> dict[str, str]:
    response = session.get(f"{base_url}/adminLegacy/data.php?parent=1001&handler=172&showPages", timeout=60, verify=False)
    response.raise_for_status()
    mapping: dict[str, str] = {}
    for match in re.finditer(r"id=(\d+)&action=edit&handler=172.*?<a href='#'>(.*?)</a>", response.text, re.S):
        title = re.sub(r"\s+", " ", html.unescape(match.group(2))).strip()
        if title:
            mapping[title] = match.group(1)
    return mapping


def save_topic(session: requests.Session, base_url: str, topic: dict[str, str], index: int, existing_id: str | None) -> dict[str, Any]:
    record_id = existing_id or "addnew"
    edit_url = (
        f"{base_url}/adminLegacy/edit.php?id={record_id}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
        if existing_id
        else f"{base_url}/adminLegacy/edit.php?id=addnew&parent=1001&handler=172&checkcode=yamete_kudasai&showPages"
    )
    response = session.get(edit_url, timeout=60, verify=False)
    response.raise_for_status()
    payload = parse_form_payload(response.text)
    slug, url_parent = resolve_horoshop_slug(session, base_url, topic["title"], existing_id or "0")
    slug = slug.replace("/{id}", "").replace("{id}", "").strip("/") or slugify(topic["title"])
    image_url = IMAGES.get(topic["key"]) or IMAGES.get("water") or ""
    article_date = date(2026, 5, 30) - timedelta(days=index * 3 + (index % 4))
    body = render_article(topic, index)
    announce = f"Великий практичний матеріал про {topic['kind']}: як вибирати, що перевіряти перед покупкою і як не купити зайве."
    payload.update(
        {
            "checkcode": "yamete_kudasai",
            "id": record_id,
            "handler": "172",
            "handlertable": "h_news",
            "back": "index.php",
            "names[act]": "1",
            "names[parent]": "1001",
            "names[date]": article_date.isoformat(),
            "names[name][slug]": slug,
            "names[name][parent]": url_parent,
            "names[img][id]": "3519",
            "names[img][value]": public_to_hidden(image_url),
            "names[i18n][3][title]": topic["title"],
            "names[i18n][3][announce]": announce,
            "names[i18n][3][text]": body,
            "names[i18n][3][h1_title]": topic["title"],
            "names[i18n][3][seo_title]": f"{topic['title']} | Все для рибалки",
            "names[i18n][3][seo_keywords]": f"{topic['kind']}, риболовля, снасті, все для рибалки",
            "names[i18n][3][seo_description]": announce,
            "names[promo]": "0",
            "names[disallow_comments]": "0",
        }
    )
    if "names[cover][id]" in payload:
        payload["names[cover][value]"] = public_to_hidden(image_url)
    save = session.post(
        f"{base_url}/adminLegacy/save.php",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": edit_url},
        timeout=60,
        verify=False,
        allow_redirects=True,
    )
    save.raise_for_status()
    return {
        "title": topic["title"],
        "id": existing_id or "",
        "slug": slug,
        "date": article_date.isoformat(),
        "image_key": topic["key"],
        "image_value": public_to_hidden(image_url),
        "chars": len(body),
        "status": save.status_code,
        "mode": "updated" if existing_id else "created",
    }


def inspect_records(session: requests.Session, base_url: str, max_id: int = 140) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for record_id in range(37, max_id + 1):
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
                "act": payload.get("names[act]"),
                "title": title,
                "slug": payload.get("names[name][slug]"),
                "date": payload.get("names[date]"),
                "img": payload.get("names[img][value]"),
                "chars": len(body),
                "ul_count": body.lower().count("<ul"),
                "image_count": len(re.findall(r"<img\b", body, re.I)),
            }
        )
    return records


def main() -> int:
    env = load_env()
    base_url = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-blog-full-upgrade/1.0"
    session.post(
        f"{base_url}/core-api/admin/security/login",
        json={"login": env["HOROSHOP_LOGIN"], "password": env["HOROSHOP_PASS"]},
        timeout=60,
        verify=False,
    ).raise_for_status()

    existing = title_ids(session, base_url)
    saved = [save_topic(session, base_url, topic, index, existing.get(topic["title"])) for index, topic in enumerate(TOPICS)]
    records = inspect_records(session, base_url)
    active = [record for record in records if record.get("act") == "1"]
    public_checks = []
    for record in active:
        slug = str(record.get("slug") or "").strip("/")
        response = session.get(f"{base_url}/{slug}/?codex_full_blog_verify=1", timeout=60, verify=False)
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
    blog = session.get(f"{base_url}/blog/?codex_blog_preview_verify=1", timeout=60, verify=False)
    report = {
        "saved_count": len(saved),
        "saved": saved,
        "active_count": len(active),
        "active_records": active,
        "public_checks": public_checks,
        "bad": [
            item for item in public_checks
            if item["status"] != 200
            or not item["has_title"]
            or int(item["image_count"]) < 1
            or not item.get("preview_img")
            or int(item.get("body_chars") or 0) < 7500
            or int(item.get("ul_count") or 0) > 0
        ],
        "blog_list_status": blog.status_code,
        "blog_list_camera_placeholders": blog.text.count("noPhoto") + blog.text.count("camera"),
        "unique_preview_images": len({str(record.get("img")) for record in active if record.get("img")}),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["saved_count", "active_count", "unique_preview_images", "blog_list_status", "blog_list_camera_placeholders", "bad"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
