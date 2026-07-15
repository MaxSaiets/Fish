"""
Заповнення SEO-контенту категорій Horoshop:
  - seo_text (текст внизу сторінки категорії, i18n locale 3 = ua) — зараз ПОРОЖНІЙ у всіх
  - seo_title / seo_description / h1_title — покращені формули за аналізом конкурентів
    (data/competitor_content_rules_20260610.md)

Механізм: той самий, що в apply_horoshop_menu_fixes.py — requests + legacy edit.php/save.php
(handler=4, дерево каталогу від root id=97). Жодних змін назв/меню/слагів.

Запуск:
  python src\\fill_category_seo.py --list           # просто зібрати дерево категорій
  python src\\fill_category_seo.py --ids 1098       # тест на одній категорії
  python src\\fill_category_seo.py --limit 3        # перші 3
  python src\\fill_category_seo.py                  # всі категорії
Звіт: data/category_seo_fill_report_YYYYMMDD.json
"""
from __future__ import annotations

import argparse
import hashlib
import html as html_mod
import json
import re
import sys
import urllib.parse
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

from apply_horoshop_menu_fixes import (  # noqa: E402
    LegacyFormParser,
    auth,
    get_base_url,
    load_env,
    post_form,
)

CATALOG_ROOT = "97"
SHOP_NAME = "Все для рибалки"


# ---------------------------------------------------------------- категорії

class PagesListParser(HTMLParser):
    """Витягує (id, parent, title) з листингу data.php?handler=4&parent=X.
    Шукаємо посилання на edit.php?id=NNN&parent=MMM."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._cur: tuple[str, str] | None = None
        self._text: list[str] = []
        self.titles: dict[str, str] = {}

    def handle_starttag(self, tag, attrs_raw):
        attrs = dict(attrs_raw)
        if tag == "a":
            href = attrs.get("href") or ""
            m = re.search(r"edit\.php\?id=(\d+)&(?:amp;)?parent=(\d+)", href)
            if m:
                self._cur = (m.group(1), m.group(2))
                self._text = []

    def handle_data(self, data):
        if self._cur:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._cur:
            title = " ".join("".join(self._text).split())
            cid, parent = self._cur
            if title and cid not in self.titles:
                self.titles[cid] = title
                self.links.append((cid, parent))
            self._cur = None


def walk_categories(session: requests.Session, base_url: str) -> list[dict]:
    """Сторінка data.php?handler=4 містить ВСЕ дерево сторінок одразу.
    Назва:  <a href='...data.php?parent={ID}&handler=381...'>Назва</a>  (лінк на товари)
    Parent: <a class='content' href='...edit.php?id={ID}&parent={PARENT}&handler=4...'>
    Категорії каталогу = ті, чий products-лінк має handler=381, під коренем 97."""
    url = f"{base_url}/adminLegacy/data.php?handler=4&checkcode=yamete_kudasai"
    r = session.get(url, timeout=30, verify=False)
    r.raise_for_status()
    html = r.text

    titles: dict[str, str] = {}
    for cid, title in re.findall(
        r"data\.php\?parent=(\d+)&handler=381&showPages'>([^<]+)</a>", html
    ):
        titles[cid] = " ".join(title.split())

    parents: dict[str, str] = {}
    for cid, parent in re.findall(
        r"edit\.php\?id=(\d+)&parent=(\d+)&handler=4", html
    ):
        parents.setdefault(cid, parent)

    out: list[dict] = []
    for cid, title in titles.items():
        parent = parents.get(cid, CATALOG_ROOT)
        out.append({"id": cid, "parent": parent, "title": title})

    # тільки ті, що в піддереві кореня каталогу 97
    children: dict[str, list[str]] = {}
    for c in out:
        children.setdefault(c["parent"], []).append(c["id"])
    keep: set[str] = set()
    stack = [CATALOG_ROOT]
    while stack:
        node = stack.pop()
        for ch in children.get(node, []):
            if ch not in keep:
                keep.add(ch)
                stack.append(ch)
    return [c for c in out if c["id"] in keep]


# ---------------------------------------------------------------- контент

def pick(seed: str, options: list[str]) -> str:
    digest = hashlib.md5(seed.encode("utf-8", "ignore")).digest()
    return options[digest[0] % len(options)]


THEMES: list[tuple[tuple[str, ...], dict]] = [
    ((u"вудилищ", u"вудки", u"спінінг", u"фідер", u"короповi", u"коропові", u"махов"), {
        "what": "вудилище",
        "choose": [
            "довжину під дистанцію ловлі та ширину водойми",
            "тест бланка під вагу приманок чи годівниць",
            "стрій — швидкий для точності, повільніший для дальності та виважування",
            "матеріал бланка: карбон легший і чутливіший, композит міцніший і дешевший",
            "транспортну довжину, якщо часто їздите на риболовлю громадським транспортом",
        ],
        "types": "Спінінгові моделі розраховані на активну ловлю хижака, фідерні — на донну "
                 "ловлю з годівницею, коропові тримають потужні навантаження на виважуванні, "
                 "а махові та болонські підходять для класичної поплавкової риболовлі.",
    }),
    ((u"котушк",), {
        "what": "котушка",
        "choose": [
            "розмір шпулі (1000-2500 для ультралайту, 2500-4000 для універсальної ловлі, 4000+ для фідера та коропа)",
            "передаточне число: швидкісні для активних проводок, силові для важких умов",
            "кількість та якість підшипників",
            "тип фрикціона — передній точніший, задній зручніший для швидких змін",
            "наявність байтранера для коропової ловлі",
        ],
        "types": "Безінерційні котушки — універсальний вибір для більшості видів ловлі; "
                 "мультиплікатори дають перевагу на важких приманках і троллінгу.",
    }),
    ((u"гачк", u"гачок"), {
        "what": "гачок",
        "choose": [
            "номер гачка під розмір насадки та очікувану рибу",
            "форму: класична для універсальної ловлі, бойлова для волосяних монтажів, офсетна для силікону",
            "товщину дроту — тонкий менше травмує насадку, товстий тримає трофей",
            "покриття: тефлон і нікель для прісної води, антикорозійні для тривалого сезону",
        ],
        "types": "Одинарні гачки закривають більшість завдань; двійники й трійники ставлять "
                 "на блешні та воблери; офсетні — основа незачіпляйок для джигу.",
    }),
    ((u"волосін", u"шнур", u"флюорокарбон", u"повідц", u"повідк", u"лідкор"), {
        "what": "волосінь чи шнур",
        "choose": [
            "діаметр і розривне навантаження під вагу риби та оснастки",
            "тип: монофіл амортизує ривки, плетений шнур дає чутливість, флюорокарбон невидимий у воді",
            "довжину розмотки під вашу котушку та запас на перев'язування",
            "колір: непомітний для риби або помітний вам для контролю проводки",
        ],
        "types": "Монофільна волосінь — вибір для поплавкової та фідерної ловлі; плетені шнури "
                 "незамінні в джигу; флюорокарбон ставлять на повідці для обережної риби.",
    }),
    ((u"бойл", u"поп-ап", u"pop", u"насадк", u"зернов", u"кукурудз", u"тісто", u"пелетс", u"пеллетс"), {
        "what": "насадка",
        "choose": [
            "розмір під номер гачка та активність дрібної риби",
            "аромат: солодкі для теплої води, рибні та спеції для холодної",
            "плавучість: тонучі для чистого дна, pop-up для мулу і трави",
            "сезонність: висока поживність влітку, легкозасвоювані інгредієнти восени та навесні",
        ],
        "types": "Варені бойли працюють як основна насадка та корм; pop-up піднімають гачок над "
                 "дном; зернові й пелетс створюють недорогий кормовий стіл.",
    }),
    ((u"прикормк", u"ліквід", u"атрактант", u"добавк", u"аром", u"мікс", u"спод"), {
        "what": "прикормка",
        "choose": [
            "фракцію: дрібна збирає дрібноту й активність, велика утримує крупну рибу",
            "механіку: пилюча для товщі води, в'язка для течії",
            "аромат і колір під сезон та прозорість води",
            "сумісність із ліквідами й бустерами для підсилення сигналу",
        ],
        "types": "Сипучі суміші — база закорму; ліквіди та атрактанти підсилюють пляму; "
                 "готові спод-мікси економлять час на змішуванні.",
    }),
    ((u"грузил", u"вантаж", u"монтаж", u"вертлюг", u"карабін", u"кільц", u"застібк", u"оснастк", u"осначтк"), {
        "what": "елемент оснастки",
        "choose": [
            "розривне навантаження фурнітури із запасом відносно волосіні",
            "розмір: дрібний для делікатних оснасток, більший для коропових монтажів",
            "форму грузила під дно: куля для твердого, грип для течії, плаский для мулу",
            "якість обертання вертлюгів — це захист від перекручування",
        ],
        "types": "Вертлюги і застібки прибирають перекручування та прискорюють переоснащення; "
                 "грузила тримають монтаж у точці; готові монтажі економлять час на березі.",
    }),
    ((u"поплав",), {
        "what": "поплавок",
        "choose": [
            "вантажопідйомність під дистанцію та глибину ловлі",
            "форму тіла: крапля для стоячої води, бочка для течії",
            "товщину антени під делікатність клювання",
            "тип кріплення для швидкої заміни",
        ],
        "types": "Спортивні поплавки дають максимальну чутливість; матчеві летять далеко; "
                 "зимові працюють у лунці з мінімальним опором.",
    }),
    ((u"сигналізатор", u"свінгер", u"індикатор", u"бубонч", u"світлячк"), {
        "what": "сигналізатор",
        "choose": [
            "тип: електронний для нічної ловлі, механічний як надійна класика",
            "чутливість і регулювання гучності",
            "комплектацію: набори з пейджером зручні для кількох вудилищ",
            "живлення та захист від вологи",
        ],
        "types": "Електронні сигналізатори звільняють очі та працюють уночі; свінгери показують "
                 "поклювки «на ослаблення»; світлячки — бюджетне рішення для вечірньої ловлі.",
    }),
    ((u"підсак", u"садок", u"карп'ятник", u"мат", u"сумк", u"чохл", u"короб", u"ящик", u"відр"), {
        "what": "аксесуар",
        "choose": [
            "розмір під вашу рибу та спосіб транспортування",
            "матеріал: безвузлова сітка для збереження риби, міцні тканини для сумок і чохлів",
            "зручність: кишені, ручки, кріплення під ваш стиль риболовлі",
        ],
        "types": "Підсаки та мати захищають рибу при виважуванні; садки зберігають улов; "
                 "сумки, чохли та коробки тримають спорядження в порядку.",
    }),
    ((u"крісл", u"стіл", u"меблі", u"розкладачк", u"парасол", u"намет"), {
        "what": "виріб для комфорту",
        "choose": [
            "вагу та габарити в складеному вигляді",
            "максимальне навантаження каркасу",
            "регулювання ніжок під нерівний берег",
            "матеріали, стійкі до вологи й ультрафіолету",
        ],
        "types": "Крісла з регульованими ніжками стоять рівно на будь-якому березі; столики "
                 "тримають прикормку та снасті під рукою; парасолі рятують від дощу і сонця.",
    }),
    ((u"одяг", u"взутт", u"костюм", u"куртк", u"термо", u"рукавиц", u"шапк", u"окуляр"), {
        "what": "екіпірування",
        "choose": [
            "розмір з урахуванням шарів одягу під низ",
            "мембранність і вологозахист під ваш сезон",
            "температурний режим для зимових костюмів",
            "зносостійкість для активної ловлі",
        ],
        "types": "Демісезонні костюми закривають більшість виїздів; зимові комплекти тримають "
                 "тепло на льоду; поляризаційні окуляри прибирають відблиски з води.",
    }),
    ((u"зимов", u"мормишк", u"балансир", u"блешн", u"кивк", u"вертушк", u"воблер", u"силікон", u"джиг", u"твістер"), {
        "what": "приманка",
        "choose": [
            "розмір і вагу під глибину та дистанцію",
            "колір: натуральні для прозорої води, яскраві для каламутної",
            "тип гри під активність риби",
            "гачки та фурнітуру — від них залежить реалізація поклювок",
        ],
        "types": "Блешні й воблери закривають активний пошук хижака; силікон — основа джигу; "
                 "мормишки та балансири — зимова класика.",
    }),
]

DEFAULT_THEME = {
    "what": "товар",
    "choose": [
        "відповідність характеристик вашим умовам ловлі",
        "якість матеріалів і фурнітури",
        "сумісність з рештою вашого спорядження",
    ],
    "types": "В асортименті — перевірені виробники та робочі моделі для різних видів риболовлі.",
}


def theme_for(title: str) -> dict:
    low = title.lower()
    for keys, theme in THEMES:
        if any(k in low for k in keys):
            return theme
    return DEFAULT_THEME


def build_seo_text(title: str) -> str:
    theme = theme_for(title)
    t = html_mod.escape(title)
    tl = html_mod.escape(title.lower())
    seed = title

    intro_pool = [
        f"У риболовлі дрібниць не буває: правильно підібране спорядження — половина успіху. "
        f"У розділі «{t}» ми зібрали перевірені моделі, з якими можна впевнено їхати і на "
        f"найближчий став, і на велику воду.",
        f"{t} в каталозі «{SHOP_NAME}» — це асортимент, який ми підбираємо за принципом "
        f"«самі б ловили з цим»: робочі характеристики, чесна ціна та наявність на складі.",
        f"Шукаєте {tl}? У цьому розділі — актуальний вибір з наявністю, реальними фото "
        f"та характеристиками, за якими легко порівняти моделі між собою.",
    ]
    why_pool = [
        f"Замовлення відправляємо Новою поштою по всій Україні, зазвичай у день оплати. "
        f"Перед відправкою перевіряємо комплектацію, а на питання щодо вибору відповідаємо "
        f"людською мовою — без завчених скриптів.",
        f"Ми — магазин рибалок для рибалок: підкажемо, що реально працює на наших водоймах, "
        f"і не радитимемо зайвого. Доставка по Україні Новою поштою, обмін і повернення "
        f"протягом 14 днів згідно із законом.",
    ]
    choose_items = "".join(f"<li>{html_mod.escape(c)}</li>" for c in theme["choose"])

    return (
        f"<p>{pick(seed + '|i', intro_pool)}</p>"
        f"<h2>Як вибрати: на що звернути увагу</h2>"
        f"<ul>{choose_items}</ul>"
        f"<p>{html_mod.escape(theme['types'])}</p>"
        f"<h2>Чому купують у нас</h2>"
        f"<p>{pick(seed + '|w', why_pool)}</p>"
    )


def build_meta(title: str) -> dict[str, str]:
    tl = title.lower()
    seo_title = f"{title} — купити в Україні, ціни від виробника | {SHOP_NAME}"
    if len(seo_title) > 75:
        seo_title = f"{title} — купити в Україні | {SHOP_NAME}"
    seo_description = (
        f"{title} в наявності в інтернет-магазині «{SHOP_NAME}» ✓ Перевірені бренди ✓ "
        f"Доставка Новою поштою по Україні ✓ Обмін 14 днів. Обирайте {tl} за характеристиками."
    )[:250]
    return {
        "seo_title": seo_title,
        "seo_description": seo_description,
        "seo_keywords": f"{tl}, купити {tl}, {tl} ціна, {tl} Україна",
        "h1_title": title,
    }


# ---------------------------------------------------------------- збереження

def fetch_form(session: requests.Session, base_url: str, cid: str, parent: str) -> dict[str, str]:
    url = (
        f"{base_url}/adminLegacy/edit.php?id={urllib.parse.quote(cid)}"
        f"&parent={urllib.parse.quote(parent)}&handler=4&checkcode=yamete_kudasai&showPages"
    )
    r = session.get(url, timeout=30, verify=False)
    r.raise_for_status()
    parser = LegacyFormParser()
    parser.feed(r.text)
    return dict(parser.fields)


def save_category_seo(session: requests.Session, base_url: str, cid: str, parent: str, title: str) -> str:
    payload = fetch_form(session, base_url, cid, parent)
    if "names[i18n][3][title]" not in payload:
        raise RuntimeError(f"Category {cid}: no editable form")
    real_title = payload.get("names[i18n][3][title]") or title
    meta = build_meta(real_title)
    payload.update({
        "checkcode": "yamete_kudasai",
        "id": cid,
        "handler": "4",
        "handlertable": "pages",
        "back": "index.php",
        "names[i18n][3][seo_title]": meta["seo_title"],
        "names[i18n][3][seo_description]": meta["seo_description"],
        "names[i18n][3][seo_keywords]": meta["seo_keywords"],
        "names[i18n][3][h1_title]": meta["h1_title"],
        "extra_parent[i18n][3][seo_text]": build_seo_text(real_title),
    })
    r = post_form(
        session,
        f"{base_url}/adminLegacy/save.php",
        payload,
        f"{base_url}/adminLegacy/edit.php?id={cid}&parent={parent}&handler=4",
    )
    return r.url


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="Лише зібрати дерево категорій")
    ap.add_argument("--ids", type=str, default=None, help="Конкретні id через кому")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    env = load_env()
    base_url = get_base_url(env)
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-category-seo/1.0"
    auth(session, base_url, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    cats = walk_categories(session, base_url)
    print(f"Дерево каталогу: {len(cats)} категорій")
    tree_path = ROOT / "data" / "category_tree_site.json"
    tree_path.write_text(json.dumps(cats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {tree_path}")
    if args.list:
        for c in cats[:30]:
            print(f"  {c['id']} (parent {c['parent']}): {c['title']}")
        return 0

    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",")}
        cats = [c for c in cats if c["id"] in wanted]
    if args.limit:
        cats = cats[: args.limit]

    report = {"started": datetime.now().isoformat(), "total": len(cats), "ok": [], "failed": []}
    for i, c in enumerate(cats, 1):
        try:
            save_category_seo(session, base_url, c["id"], c["parent"], c["title"])
            report["ok"].append(c["id"])
            print(f"[{i}/{len(cats)}] OK {c['id']} {c['title']}")
        except Exception as exc:
            report["failed"].append({"id": c["id"], "title": c["title"], "error": str(exc)})
            print(f"[{i}/{len(cats)}] FAIL {c['id']} {c['title']}: {exc}")

    report["finished"] = datetime.now().isoformat()
    out = ROOT / "data" / f"category_seo_fill_report_{datetime.now().strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Звіт: {out} | ok={len(report['ok'])} failed={len(report['failed'])}")
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
