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
        {"name": "Вудилища", "subcategories": [{"name": "Коропові"}, {"name": "Фідерні"}, {"name": "Спінінгові"}, {"name": "Махові"}, {"name": "Болонські"}, {"name": "Запчастини до вудилищ"}]},
        {"name": "Котушки", "subcategories": [{"name": "Коропові"}, {"name": "Фідерні"}, {"name": "Спінінгові"}, {"name": "Безінерційні котушки"}, {"name": "аксесуари до котушок"}]},
        {"name": "Волосінь та шнури", "subcategories": [{"name": "волосінь"}, {"name": "повідковий матеріал"}, {"name": "шнури"}, {"name": "флюорокарбон"}, {"name": "готові повідці"}]},
        {"name": "Чохли", "subcategories": [{"name": "всі"}]},
        {"name": "Гачки", "subcategories": [{"name": "спінінгові", "subcategories": [{"name": "одинарні"}, {"name": "трійники"}, {"name": "двійники"}, {"name": "офсетні"}]}, {"name": "коропові"}, {"name": "звичайні"}]},
        {"name": "Готові монтажі", "subcategories": [{"name": "оранж"}, {"name": "інші"}]},
        {"name": "Все для монтажу", "subcategories": [{"name": "карабіни вертлюги та кільця"}, {"name": "кормушки"}, {"name": "грузила", "subcategories": [{"name": "спінінгові"}, {"name": "коропові"}]}, {"name": "інше для оснащення (+стопорки)"}]},
        {"name": "Сигналізатори клювання", "subcategories": [{"name": "механічні"}, {"name": "електронні"}, {"name": "свінгери"}, {"name": "кивок"}]},
        {"name": "Насадочні", "subcategories": [{"name": "бойли"}, {"name": "поп-ап"}, {"name": "діпи"}, {"name": "зернові"}]},
        {"name": "Прикормка", "subcategories": [{"name": "фанатік", "subcategories": [{"name": "Кекси"}, {"name": "все скопом"}]}, {"name": "анві"}, {"name": "реал фіш"}, {"name": "інтеркріл"}, {"name": "інші бренди"}, {"name": "технопланктон"}, {"name": "макуха"}, {"name": "зернові"}]},
        {"name": "Пелетси", "subcategories": [{"name": "боунті"}, {"name": "анві"}, {"name": "фанатік"}, {"name": "бум"}, {"name": "рпф"}, {"name": "пугач"}, {"name": "інші бренди"}]},
        {"name": "ліквіди і атрактанти", "subcategories": [{"name": "всі"}]},
        {"name": "Відра, сумки та органайзери", "subcategories": [{"name": "відра"}, {"name": "коробки органайзери"}, {"name": "сумки"}, {"name": "повідочниці"}]},
        {"name": "підставки та тримачі", "subcategories": [{"name": "родподи"}, {"name": "підставки та триноги"}, {"name": "аксесуари"}]},
        {"name": "Підсаки, Садки, кукани", "subcategories": [{"name": "Підсаки"}, {"name": "ручки та голови до підсака"}, {"name": "Садки кукани"}]},
        {"name": "Крісла, стільці та столи", "subcategories": [{"name": "крісла"}, {"name": "стільці"}, {"name": "столи"}]},
        {"name": "PVA матеріали та аксесуари", "subcategories": [{"name": "PVA"}, {"name": "Інструменти"}]},
        {"name": "Зимова ловля", "subcategories": [{"name": "жерлиці"}, {"name": "льодобури"}, {"name": "мотильниці"}, {"name": "мормишки"}, {"name": "вудилища"}, {"name": "набори жерлиць"}, {"name": "сані"}, {"name": "ящики"}, {"name": "костюми зимові"}, {"name": "аксесуари"}, {"name": "жилка зимова"}, {"name": "льодоступи"}]},
        {"name": "Туризм", "subcategories": [{"name": "ліхтарі"}, {"name": "посуд"}, {"name": "термоси"}, {"name": "плити, горілки балони"}, {"name": "батарейки"}]},
        {"name": "Приманки", "subcategories": [{"name": "балансири"}, {"name": "блешні"}, {"name": "мандула"}, {"name": "воблери"}]},
    ],
}

PLACEHOLDER_CATEGORIES = {"Ваш тип товарів чи послуг", "Ваша група товарів чи послуг", "Нова група"}
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


def map_product_to_target_path(product: dict[str, Any]) -> str:
    category_path = [
        str(item).strip()
        for item in (product.get("category_path") or [])
        if str(item).strip() and str(item).strip() not in PLACEHOLDER_CATEGORIES
    ]
    top = category_path[0] if category_path else ""
    name = str(product.get("name") or "").lower()

    if top == "Спінінг":
        return "Вудилища / Спінінгові"
    if top == "Вудки":
        return "Вудилища / Махові"
    if top == "Зернові":
        return "Насадочні / зернові"
    if top == "Волосінь":
        return "Волосінь та шнури / волосінь"
    if top == "Повідці":
        return "Волосінь та шнури / готові повідці"
    if top == "Флюрокарбон":
        return "Волосінь та шнури / флюорокарбон"
    if top == "Кивки":
        return "Сигналізатори клювання / кивок"
    if top == "Сигналізатори":
        if "електрон" in name:
            return "Сигналізатори клювання / електронні"
        if "свінгер" in name:
            return "Сигналізатори клювання / свінгери"
        return "Сигналізатори клювання / механічні"
    return "Приманки / воблери"


def build_real_product_payloads() -> list[dict[str, Any]]:
    data = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))
    items: list[dict[str, Any]] = []
    for p in data.get("products", []):
        kod = str(p.get("kod") or "").strip()
        name = str(p.get("name") or "").strip()
        if not kod or not name or name in SKIP_NAMES:
            continue
        price = p.get("cena_r") or p.get("cena_o") or 0
        qty = int(round(float(p.get("stock") or 0)))
        brand = str(p.get("proizv") or "").strip()
        desc = str(p.get("descr_big") or "").strip()
        parent_path = map_product_to_target_path(p)
        item: dict[str, Any] = {
            "article": kod,
            "title": name,
            "price": float(price),
            "quantity": max(0, qty),
            "parent": parent_path,
            "parent_article": kod,
            "display_in_showcase": 1,
            "presence": "in stock" if qty > 0 else "out of stock",
            "currency": "UAH",
        }
        if brand:
            item["brand"] = brand
        if desc:
            item["description"] = desc
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
