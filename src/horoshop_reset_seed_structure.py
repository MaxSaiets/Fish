from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import requests
import urllib3

urllib3.disable_warnings()

ROOT = Path(r"D:\FISH\fish-sync")
PRODUCTS_JSON = ROOT / "data" / "products.json"
ENV_FILE = ROOT / ".env"


STRUCTURE = {
    "site_name": "СТРУКТУРА САЙТУ “ВСЕ ДЛЯ РИБАЛКИ”",
    "categories": [
        {"name": "Херабуна", "subcategories": [{"name": "вудилища"}, {"name": "готові оснастки"}, {"name": "тісто"}, {"name": "аксесуари"}, {"name": "підсак, садок"}, {"name": "стільці"}, {"name": "поплавки"}, {"name": "набори"}, {"name": "поплавочниці, чохли та органайзери"}, {"name": "гачки і повідки"}]},
        {"name": "Вудилища", "subcategories": [{"name": "Коропові"}, {"name": "Фідерні"}, {"name": "Спінінгові"}, {"name": "Махові"}, {"name": "Болонські"}, {"name": "Запчастини та аксесуари для вудок"}]},
        {"name": "Котушки", "subcategories": [{"name": "Коропові"}, {"name": "Фідерні"}, {"name": "Спінінгові"}, {"name": "Безінерційні котушки"}, {"name": "аксесуари до котушок"}]},
        {"name": "Волосінь та шнури", "subcategories": [{"name": "волосінь"}, {"name": "повідковий матеріал"}, {"name": "шнури"}, {"name": "флюорокарбон"}, {"name": "готові повідці"}]},
        {"name": "Чохли", "subcategories": [{"name": "всі"}]},
        {"name": "Гачки", "subcategories": [{"name": "спінінгові", "subcategories": [{"name": "одинарні"}, {"name": "трійники"}, {"name": "двійники"}, {"name": "офсетні"}]}, {"name": "коропові"}]},
        {"name": "Готові монтажі", "subcategories": [{"name": "оранж"}, {"name": "інші"}]},
        {"name": "Все для монтажу", "subcategories": [{"name": "карабіни вертлюги та кільця"}, {"name": "Годівниці"}, {"name": "грузила", "subcategories": [{"name": "спінінгові"}, {"name": "коропові"}]}, {"name": "Інше для оснащення"}]},
        {"name": "Сигналізатори клювання", "subcategories": [{"name": "механічні"}, {"name": "електронні"}, {"name": "свінгери"}, {"name": "кивок"}]},
        {"name": "Насадочні", "subcategories": [{"name": "бойли"}, {"name": "поп-ап"}, {"name": "діпи"}, {"name": "зернові"}]},
        {"name": "Прикормка", "subcategories": [{"name": "Fanatik", "subcategories": [{"name": "Кекси"}, {"name": "все скопом"}]}, {"name": "Anvi"}, {"name": "Real Fish"}, {"name": "Interkril"}, {"name": "Інші бренди"}, {"name": "Технопланктон"}, {"name": "Макуха"}, {"name": "Зернові"}]},
        {"name": "Пелетси", "subcategories": [{"name": "Bounty"}, {"name": "Anvi"}, {"name": "Fanatik"}, {"name": "Boom"}, {"name": "RPF"}, {"name": "Puhach"}, {"name": "Інші бренди"}]},
        {"name": "ліквіди і атрактанти", "subcategories": [{"name": "всі"}]},
        {"name": "Відра, сумки та органайзери", "subcategories": [{"name": "відра"}, {"name": "коробки органайзери"}, {"name": "сумки"}, {"name": "повідочниці"}]},
        {"name": "підставки та тримачі", "subcategories": [{"name": "родподи"}, {"name": "підставки та триноги"}, {"name": "аксесуари"}]},
        {"name": "Підсаки, Садки, кукани", "subcategories": [{"name": "Підсаки"}, {"name": "ручки та голови до підсака"}, {"name": "Садки кукани"}]},
        {"name": "Крісла, стільці та столи", "subcategories": [{"name": "крісла"}, {"name": "стільці"}, {"name": "столи"}]},
        {"name": "PVA матеріали та аксесуари", "subcategories": [{"name": "PVA матеріали"}, {"name": "Інструменти"}]},
        {"name": "Зимова ловля", "subcategories": [{"name": "жерлиці"}, {"name": "льодобури"}, {"name": "мотильниці"}, {"name": "мормишки"}, {"name": "вудилища"}, {"name": "набори жерлиць"}, {"name": "сані"}, {"name": "ящики"}, {"name": "костюми зимові"}, {"name": "аксесуари"}, {"name": "жилка зимова"}, {"name": "льодоступи"}]},
        {"name": "Туризм", "subcategories": [{"name": "ліхтарі"}, {"name": "посуд"}, {"name": "термоси"}, {"name": "плити, горілки балони"}, {"name": "батарейки"}, {"name": "одяг та взуття"}]},
        {"name": "Подарункові сертифікати", "subcategories": [{"name": "всі"}]},
        {"name": "Приманки", "subcategories": [{"name": "балансири"}, {"name": "блешні"}, {"name": "мандула"}, {"name": "воблери"}]},
    ],
}

PLACEHOLDER_CATEGORIES = {
    "Ваш тип товарів чи послуг", "Ваша група товарів чи послуг",
    "Нова група", "Новая группа", "Новая  ", "Нова ", "Нова",
}
SKIP_NAMES = {"Повна назва товару", "test", "tetg", "Мій товар"}


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def get_base_url(env: dict[str, str]) -> str:
    explicit = env.get("HOROSHOP_BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    domain = env.get("HOROSHOP_DOMAIN", "shop645299.horoshop.ua").strip()
    if domain.startswith("http://") or domain.startswith("https://"):
        return domain.rstrip("/")
    return f"https://{domain}".rstrip("/")


def auth(session: requests.Session, base_url: str, login: str, password: str) -> str:
    response = session.post(
        f"{base_url}/api/auth/",
        json={"login": login, "password": password},
        verify=False,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    token = data.get("token") or (data.get("response") or {}).get("token")
    if data.get("status") != "OK" or not token:
        raise RuntimeError(f"Auth failed: {json.dumps(data, ensure_ascii=False)}")
    return str(token)


def api_post(session: requests.Session, base_url: str, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = session.post(f"{base_url}{endpoint}", json=payload, verify=False, timeout=60)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid API response for {endpoint}: {data!r}")
    return data


def chunked(items: list[dict[str, Any]], size: int = 100) -> list[list[dict[str, Any]]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def export_catalog(session: requests.Session, base_url: str, token: str) -> list[dict[str, Any]]:
    data = api_post(session, base_url, "/api/catalog/export/", {"token": token})
    if data.get("status") != "OK":
        raise RuntimeError(f"catalog/export failed: {json.dumps(data, ensure_ascii=False)}")
    return list(((data.get("response") or {}).get("products")) or [])


def flatten_leaf_paths(categories: list[dict[str, Any]], prefix: list[str] | None = None) -> list[str]:
    prefix = prefix or []
    out: list[str] = []
    for node in categories:
        name = str(node.get("name") or "").strip()
        if not name:
            continue
        path = prefix + [name]
        children = [c for c in (node.get("subcategories") or []) if isinstance(c, dict)]
        if children:
            out.extend(flatten_leaf_paths(children, path))
        else:
            out.append(" / ".join(path))
    return out


def map_product_to_target_path(product: dict[str, Any]) -> str:  # noqa: C901
    category_path = [
        str(item).strip()
        for item in (product.get("category_path") or [])
        if str(item).strip() and str(item).strip() not in PLACEHOLDER_CATEGORIES
    ]
    name = str(product.get("name") or "").lower()

    if not category_path:
        return "Приманки / воблери"

    top = category_path[0]
    t = top.lower()
    s = category_path[1].lower() if len(category_path) > 1 else ""
    r = category_path[2].lower() if len(category_path) > 2 else ""

    # ── Спінінги і вудки ──────────────────────────────────────────────────
    if t in ("спінінги і вудки", "фідерні удочки"):
        if "спінінг" in s:           return "Вудилища / Спінінгові"
        if "махові" in s:            return "Вудилища / Махові"
        if "фіерні" in s or "фідерні" in s: return "Вудилища / Фідерні"
        if "коропові" in s:          return "Вудилища / Коропові"
        if "аксесуари" in s:         return "Вудилища / Запчастини та аксесуари для вудок"
        if "болонськ" in s:          return "Вудилища / Болонські"
        return "Вудилища / Спінінгові"

    # ── Котушки ───────────────────────────────────────────────────────────
    if t == "катушки":
        if "карпові" in s:           return "Котушки / Коропові"
        if "фідерні" in s:           return "Котушки / Фідерні"
        if "спінінгові" in s:        return "Котушки / Спінінгові"
        if "інерційні" in s:         return "Котушки / Безінерційні котушки"
        if "аксесуари" in s:         return "Котушки / аксесуари до котушок"
        return "Котушки / Спінінгові"

    # ── Волосінь / шнури / повідці ────────────────────────────────────────
    if "волосінь шнури" in t or t == "волосінь шнури повіці":
        if "шнур" in s:              return "Волосінь та шнури / шнури"
        if "ліска" in s:             return "Волосінь та шнури / волосінь"
        if "флюр" in s:              return "Волосінь та шнури / флюорокарбон"
        if "поводочний" in s or "повідков" in s: return "Волосінь та шнури / повідковий матеріал"
        if "повідці" in s or "поводок" in s:    return "Волосінь та шнури / готові повідці"
        return "Волосінь та шнури / волосінь"

    # ── Оснащення / Монтаж ────────────────────────────────────────────────
    if t == "оснащення монтаж":
        if "гачки" in s:
            if "офсетні" in r:       return "Гачки / спінінгові / офсетні"
            if "трійники" in r:      return "Гачки / спінінгові / трійники"
            if "двійники" in r:      return "Гачки / спінінгові / двійники"
            return "Гачки"
        if "вертлюги" in s or "застібки" in s:  return "Все для монтажу / карабіни вертлюги та кільця"
        if "вантажі" in s:
            if "коропов" in name:    return "Все для монтажу / грузила / коропові"
            return "Все для монтажу / грузила / спінінгові"
        if "годівниці" in s:         return "Все для монтажу / Годівниці"
        if "готові монтажі" in s:    return "Готові монтажі / інші"
        if "orange" in s:            return "Готові монтажі / оранж"
        if "поплавки" in s:          return "Херабуна / поплавки"
        if "пва" in s:               return "PVA матеріали та аксесуари / PVA матеріали"
        if "головки" in s:           return "Все для монтажу / Інше для оснащення"
        return "Все для монтажу / Інше для оснащення"

    # ── Спінінгова ловля (приманки) ───────────────────────────────────────
    if t == "спінінгова ловля":
        if "блесна" in s:            return "Приманки / блешні"
        if "воблер" in s:            return "Приманки / воблери"
        if "силіконова" in s:        return "Приманки / мандула"
        if "mepps" in s:             return "Приманки / блешні"
        if "тел-спіннер" in s:       return "Приманки / блешні"
        if "балансир" in s:          return "Приманки / балансири"
        if "мормишка" in s or "грушка" in s: return "Приманки / мандула"
        if "кейтеч" in s:            return "Приманки / мандула"
        if "аксесуари" in s:         return "Вудилища / Запчастини та аксесуари для вудок"
        return "Приманки / воблери"

    # ── Херабуна ──────────────────────────────────────────────────────────
    if t == "херабуна":
        if "вудочка" in s or "вудилищ" in s:   return "Херабуна / вудилища"
        if "тісто" in s:             return "Херабуна / тісто"
        if "поплавок" in s:          return "Херабуна / поплавки"
        if "оснащення" in s:         return "Херабуна / готові оснастки"
        if "гачки" in s or "волосінь" in s:    return "Херабуна / гачки і повідки"
        if "підсак" in s:            return "Херабуна / підсак, садок"
        if "стілець" in s or "стільці" in s:   return "Херабуна / стільці"
        return "Херабуна / аксесуари"

    # ── Прикормка (загальна категорія) ────────────────────────────────────
    if t == "прикормка":
        if "бойли" in s:             return "Насадочні / бойли"
        if "кукуруза" in s or "горох" in s:    return "Насадочні / зернові"
        if "наживка" in s or "пінопласт" in s: return "Насадочні / поп-ап"
        if "пеллетс" in s or "пелетс" in s:   return "Пелетси / Інші бренди"
        if "ароматизатор" in s:      return "ліквіди і атрактанти / всі"
        if "пінотісто" in s or "макуха" in s or "планктон" in s:
            if "макуха" in r:        return "Прикормка / Макуха"
            if "планктон" in r or "технопланктон" in r: return "Прикормка / Технопланктон"
            return "Прикормка / Технопланктон"
        if "прикормка" in s:
            if "interkril" in r:     return "Прикормка / Interkril"
            return "Прикормка / Інші бренди"
        return "Прикормка / Інші бренди"

    if t == "сертифікати":
        return "Подарункові сертифікати / всі"

    # ── Бренди насадок / пелетсів ─────────────────────────────────────────
    if t == "rpf":
        if "поп ап" in s or "бойл" in s:       return "Насадочні / поп-ап"
        if "пелетс" in s or "гранула" in s:    return "Пелетси / RPF"
        if "пва" in s:               return "PVA матеріали та аксесуари / PVA матеріали"
        return "Пелетси / RPF"

    if t == "boom":
        if "горох" in s or "кукурудза" in s:   return "Насадочні / зернові"
        if "пелетс" in s:            return "Пелетси / Boom"
        if "рідина" in s:            return "ліквіди і атрактанти / всі"
        if "прикормка" in s:         return "Прикормка / Інші бренди"
        if "пінотісто" in s:         return "Прикормка / Технопланктон"
        if "бойли" in s:             return "Насадочні / бойли"
        return "Прикормка / Інші бренди"

    if t == "puhach":
        if "поп" in s:               return "Насадочні / поп-ап"
        if "бойл" in s:              return "Насадочні / бойли"
        if "пелетс" in s:            return "Пелетси / Puhach"
        if "ліквід" in s:            return "ліквіди і атрактанти / всі"
        return "Насадочні / поп-ап"

    if t == "bounty":
        if "пелетс" in s:            return "Пелетси / Bounty"
        if "csl" in s:               return "ліквіди і атрактанти / всі"
        if "насадка" in s:           return "Насадочні / поп-ап"
        if "stick sauce" in s:       return "ліквіди і атрактанти / всі"
        if "ліквід" in s:            return "ліквіди і атрактанти / всі"
        return "Насадочні / поп-ап"

    if t == "3k":
        if "поп ап" in s:            return "Насадочні / поп-ап"
        if "зернові" in s or "насадочні" in s: return "Насадочні / зернові"
        if "діп" in s:               return "Насадочні / діпи"
        return "Насадочні / бойли"

    if t == "realfish":
        return "Прикормка / Real Fish"

    if "interkril" in t:
        if "поп-ап" in s or "pop-up" in s:     return "Насадочні / поп-ап"
        if "ліквід" in s:            return "ліквіди і атрактанти / всі"
        if "пелетс" in s:            return "Пелетси / Інші бренди"
        return "Прикормка / Interkril"

    if "anvifishing" in t:
        if "прикормка" in s:         return "Прикормка / Anvi"
        if "пелетс" in s:            return "Пелетси / Anvi"
        if "ліквід" in s or "спрей" in s:      return "ліквіди і атрактанти / всі"
        if "макуха" in s:            return "Прикормка / Макуха"
        return "Прикормка / Anvi"

    if t == "fanatik":
        if "прикормка" in s:         return "Прикормка / Fanatik / все скопом"
        if "пелетс" in s:            return "Пелетси / Fanatik"
        if "спрей" in s:             return "ліквіди і атрактанти / всі"
        if "кекс" in s:              return "Прикормка / Fanatik / Кекси"
        return "Прикормка / Fanatik / все скопом"

    if "fshing mix" in t or "fishing mix" in t:
        return "Прикормка / Інші бренди"

    # ── Зима ──────────────────────────────────────────────────────────────
    if t == "зима":
        if "мармишка" in s or "мормишка" in s: return "Зимова ловля / мормишки"
        if "балансир" in s:          return "Приманки / балансири"
        if "блешні" in s:            return "Зимова ловля / аксесуари"
        if "вудки" in s or "вудилища" in s:    return "Зимова ловля / вудилища"
        if "кивок" in s:             return "Зимова ловля / аксесуари"
        if "льодобур" in s or "бур" in s:      return "Зимова ловля / льодобури"
        if "волосінь" in s or "жилка" in s:    return "Зимова ловля / жилка зимова"
        if "сані" in s or "ящики" in s:        return "Зимова ловля / сані"
        if "катушки" in s:           return "Зимова ловля / аксесуари"
        return "Зимова ловля / аксесуари"

    # ── Допоміжні снасті ──────────────────────────────────────────────────
    if t == "допоміжні снасті":
        if "підсаки" in s:
            if "ручка" in r or "голова" in r:  return "Підсаки, Садки, кукани / ручки та голови до підсака"
            return "Підсаки, Садки, кукани / Підсаки"
        if "садки" in s:             return "Підсаки, Садки, кукани / Садки кукани"
        if "стільці" in s:           return "Крісла, стільці та столи / стільці"
        if "сумки" in s:
            if "поводочниці" in r:   return "Відра, сумки та органайзери / повідочниці"
            return "Відра, сумки та органайзери / сумки"
        if "ящики" in s or "коробки" in s:     return "Відра, сумки та органайзери / коробки органайзери"
        if "чохли" in s or "тубоси" in s:      return "Чохли / всі"
        if "сигналізатори" in s:
            if "кивок" in r:         return "Сигналізатори клювання / кивок"
            if "механічні" in r:     return "Сигналізатори клювання / механічні"
            if "свінгер" in r:       return "Сигналізатори клювання / свінгери"
            if "електрон" in name:   return "Сигналізатори клювання / електронні"
            return "Сигналізатори клювання / механічні"
        if "підставки" in s or "рогачі" in s or "род-поди" in s:
            if "род-под" in r:       return "підставки та тримачі / родподи"
            if "підставка" in r or "тринога" in r: return "підставки та тримачі / підставки та триноги"
            if "бузбар" in r or "гребінки" in r:   return "підставки та тримачі / аксесуари"
            if "аксесуари" in r:     return "підставки та тримачі / аксесуари"
            return "підставки та тримачі / підставки та триноги"
        if "інструменти" in s:       return "PVA матеріали та аксесуари / Інструменти"
        if "льодоруби" in s:         return "Зимова ловля / льодобури"
        return "Все для монтажу / Інше для оснащення"

    # ── Туризм ────────────────────────────────────────────────────────────
    if "туризм" in t:
        if "ліхтарі" in s:           return "Туризм / ліхтарі"
        if "посуд" in s:             return "Туризм / посуд"
        if "газове" in s:            return "Туризм / плити, горілки балони"
        if "термо" in s:             return "Туризм / термоси"
        return "Туризм / посуд"

    # ── Аксесуари (загальні) ──────────────────────────────────────────────
    if t == "аксесуари":
        if "батарейки" in s:         return "Туризм / батарейки"
        if "ножиці" in s or "спомб" in s:      return "PVA матеріали та аксесуари / Інструменти"
        return "Все для монтажу / Інше для оснащення"

    # ── Старі категорії (fallback для старої бази) ────────────────────────
    if top == "Спінінг":             return "Вудилища / Спінінгові"
    if top == "Вудки":               return "Херабуна / вудилища"
    if top == "Зернові":             return "Насадочні / зернові"
    if top == "Волосінь":            return "Волосінь та шнури / волосінь"
    if top == "Повідці":             return "Волосінь та шнури / готові повідці"
    if top == "Флюрокарбон":         return "Волосінь та шнури / флюорокарбон"
    if top == "Кивки":               return "Сигналізатори клювання / кивок"
    if top == "Сигналізатори":
        if "електрон" in name:       return "Сигналізатори клювання / електронні"
        if "свінгер" in name:        return "Сигналізатори клювання / свінгери"
        return "Сигналізатори клювання / механічні"

    return "Приманки / воблери"


def build_real_product_payloads() -> list[dict[str, Any]]:
    from horoshop_catalog import build_canonical_products

    items: list[dict[str, Any]] = []
    for product in build_canonical_products():
        item = {
            "article": product["article"],
            "title": product["title"],
            "price": float(product.get("price") or 0),
            "quantity": int(product.get("quantity") or 0),
            "parent": product["parent"],
            "parent_article": product["article"],
            "display_in_showcase": int(product.get("display_in_showcase", 1)),
            "presence": product.get("presence_api", "out of stock"),
            "currency": product.get("currency", "UAH"),
        }
        if product.get("brand"):
            item["brand"] = product["brand"]
        if product.get("description"):
            item["description"] = product["description"]
        if product.get("params"):
            item["params"] = list(product["params"])
        if product.get("images"):
            item["images"] = list(product["images"])
        items.append(item)
    return items


def import_products(session: requests.Session, base_url: str, token: str, products: list[dict[str, Any]], label: str) -> None:
    batches = chunked(products, 100)
    for i, batch in enumerate(batches, 1):
        payload = {"token": token, "products": batch}
        data = api_post(session, base_url, "/api/catalog/import/", payload)
        status = str(data.get("status") or "")
        if status not in {"OK", "WARNING"}:
            raise RuntimeError(f"{label} batch {i}/{len(batches)} failed: {json.dumps(data, ensure_ascii=False)}")
        print(f"{label}: batch {i}/{len(batches)} status={status} items={len(batch)}")


def build_hide_payloads(existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in existing:
        article = str(p.get("article") or "").strip()
        if not article:
            continue
        out.append(
            {
                "article": article,
                "display_in_showcase": 0,
                "quantity": 0,
                "presence": "out of stock",
                "parent": "Архів / Шаблонні товари",
                "parent_article": article,
            }
        )
    return out


def build_structure_seed_payloads() -> list[dict[str, Any]]:
    leaves = flatten_leaf_paths(STRUCTURE["categories"])
    payloads: list[dict[str, Any]] = []
    for idx, path in enumerate(leaves, 1):
        article = f"CAT-SEED-{idx:03d}"
        payloads.append(
            {
                "article": article,
                "title": f"Технічна категорія: {path}",
                "parent": path,
                "parent_article": article,
                "display_in_showcase": 0,
                "quantity": 0,
                "presence": "out of stock",
                "price": 1.0,
                "currency": "UAH",
            }
        )
    return payloads


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env = load_env()
    base_url = get_base_url(env)
    login = env.get("HOROSHOP_LOGIN", "").strip()
    password = env.get("HOROSHOP_PASS", "").strip()
    if not login or not password:
        raise RuntimeError("HOROSHOP_LOGIN/HOROSHOP_PASS are not configured in .env")

    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-reset-structure/1.0"
    token = auth(session, base_url, login, password)

    existing = export_catalog(session, base_url, token)
    hide_payloads = build_hide_payloads(existing)
    seed_payloads = build_structure_seed_payloads()
    real_payloads = build_real_product_payloads()

    print(f"base_url={base_url}")
    print(f"existing_products={len(existing)}")
    print(f"hide_payloads={len(hide_payloads)}")
    print(f"structure_leaf_seeds={len(seed_payloads)}")
    print(f"real_products={len(real_payloads)}")

    if args.dry_run:
        print("\n--- DRY RUN: sample of real product mappings ---")
        from collections import defaultdict
        by_parent: dict[str, list[str]] = defaultdict(list)
        for item in real_payloads:
            by_parent[item["parent"]].append(item["title"])
        for parent_path, titles in sorted(by_parent.items()):
            print(f"\n  [{parent_path}]  ({len(titles)} products)")
            for t in titles[:5]:
                print(f"    - {t}")
            if len(titles) > 5:
                print(f"    ... and {len(titles) - 5} more")
        print(f"\nTotal leaf categories used: {len(by_parent)}")
        return

    if hide_payloads:
        import_products(session, base_url, token, hide_payloads, "hide-template-products")
    if seed_payloads:
        import_products(session, base_url, token, seed_payloads, "seed-structure")
    if real_payloads:
        import_products(session, base_url, token, real_payloads, "import-real-products")

    final_catalog = export_catalog(session, base_url, token)
    visible = sum(int(p.get("display_in_showcase") or 0) for p in final_catalog)
    print(f"final_catalog_total={len(final_catalog)}")
    print(f"final_catalog_visible={visible}")


if __name__ == "__main__":
    main()
