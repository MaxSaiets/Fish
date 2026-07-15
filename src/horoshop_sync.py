"""
Синхронізація товарів з products.json -> Horoshop через офіційний API.

Логіка:
  1. Читає HOROSHOP_* з .env
  2. Отримує token через /api/auth/
  3. Готує payload для /api/catalog/import/
  4. Батчами оновлює ціну, залишок, опис, характеристики та фото товару за article
  5. Бере AI-описи та характеристики з meta_store.sqlite

Запуск:
  py src/horoshop_sync.py
  py src/horoshop_sync.py --dry-run
  py src/horoshop_sync.py --limit 10
  py src/horoshop_sync.py --skip-meta   # тільки ціни/залишки без meta_store
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).parent.parent
PRODUCTS_JSON = ROOT / "data" / "products.json"
META_DB = ROOT / "data" / "meta_store.sqlite"
ENV_FILE = ROOT / ".env"
DEFAULT_DOMAIN = "shop645299.horoshop.ua"
PLACEHOLDER_NAMES = {"Повна назва товару", "test", "tetg", "Мій товар"}
PLACEHOLDER_CATEGORIES = {"Ваш тип товарів чи послуг", "Ваша група товарів чи послуг", "Нова група", "Новая группа"}


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", html or "")).strip()


def load_meta() -> dict[str, dict]:
    """Повертає {kod: {display_name, description_html, common_params, delta_params,
                       test_min, test_max, length_m, action, pictures, brand}} """
    out: dict[str, dict] = {}
    if not META_DB.exists():
        return out
    conn = sqlite3.connect(META_DB)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT v.kod, v.test_min, v.test_max, v.length_m, v.action,
                   v.delta_params_json, v.pictures_json,
                   m.brand, m.display_name, m.description_html,
                   m.common_params_json
            FROM variants v
            JOIN models m ON m.parent_key = v.parent_key
            """
        ).fetchall()
        for r in rows:
            out[r["kod"]] = {
                "brand": r["brand"] or "",
                "display_name": r["display_name"] or "",
                "description_html": r["description_html"] or "",
                "common_params": json.loads(r["common_params_json"] or "{}"),
                "delta_params": json.loads(r["delta_params_json"] or "{}"),
                "test_min": r["test_min"],
                "test_max": r["test_max"],
                "length_m": r["length_m"],
                "action": r["action"],
                "pictures": json.loads(r["pictures_json"] or "[]"),
            }
    finally:
        conn.close()
    return out


def collect_properties(meta: dict) -> list[dict[str, str]]:
    """Будує список {name, value} для Horoshop properties."""
    params: list[tuple[str, str]] = []
    seen: set[str] = set()

    def push(key: str, value: object) -> None:
        text = str(value or "").strip()
        if not key or not text or key in seen:
            return
        params.append((key, text))
        seen.add(key)

    for key, value in (meta.get("common_params") or {}).items():
        push(key, value)
    for key, value in (meta.get("delta_params") or {}).items():
        push(key, value)
    if meta.get("test_min") is not None and meta.get("test_max") is not None:
        push("Кастинг-тест", f"{meta['test_min']:g}-{meta['test_max']:g} г")
    if meta.get("length_m"):
        push("Довжина", f"{meta['length_m']:g} м")
    if meta.get("action"):
        push("Лад", meta["action"])
    return [{"name": k, "value": v} for k, v in params]


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def as_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_base_url(env: dict[str, str]) -> str:
    explicit = env.get("HOROSHOP_BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")

    domain = env.get("HOROSHOP_DOMAIN", "").strip() or DEFAULT_DOMAIN
    if domain.startswith("http://") or domain.startswith("https://"):
        return domain.rstrip("/")

    scheme = (env.get("HOROSHOP_SCHEME", "https").strip() or "https").lower()
    return f"{scheme}://{domain}".rstrip("/")


def api_post(
    session: requests.Session,
    url: str,
    payload: dict[str, Any],
    timeout: int = 60,
) -> dict[str, Any]:
    resp = session.post(
        url,
        json=payload,
        timeout=timeout,
        headers={"Content-Type": "application/json"},
        verify=False,
    )
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"Некоректна JSON-відповідь від Horoshop: {data!r}")
    return data


def extract_token(data: dict[str, Any]) -> str:
    candidates = [
        data.get("token"),
        (data.get("response") or {}).get("token") if isinstance(data.get("response"), dict) else None,
        (data.get("response") or {}).get("auth", {}).get("token")
        if isinstance((data.get("response") or {}).get("auth"), dict)
        else None,
    ]
    for token in candidates:
        if token:
            return str(token)
    raise RuntimeError(f"Horoshop не повернув token: {json.dumps(data, ensure_ascii=False)}")


def auth(session: requests.Session, base_url: str, login: str, password: str) -> str:
    data = api_post(
        session,
        f"{base_url}/api/auth/",
        {"login": login, "password": password},
        timeout=30,
    )
    status = str(data.get("status") or "").upper()
    if status != "OK":
        raise RuntimeError(f"Помилка auth Horoshop: {json.dumps(data, ensure_ascii=False)}")
    return extract_token(data)


def load_products(limit: int | None = None) -> list[dict[str, Any]]:
    raw = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))
    deduped: dict[str, dict[str, Any]] = {}
    for product in raw.get("products", []):
        kod = str(product.get("kod") or "").strip()
        if not kod:
            continue
        name = str(product.get("name") or "").strip()
        if not name or name in PLACEHOLDER_NAMES:
            continue
        category_path = [str(item).strip() for item in (product.get("category_path") or []) if str(item).strip()]
        if category_path and all(item in PLACEHOLDER_CATEGORIES for item in category_path):
            continue
        deduped[kod] = product
        if limit and len(deduped) >= limit:
            break
    return list(deduped.values())


def get_price(product: dict[str, Any]) -> float:
    value = product.get("cena_r") or product.get("cena_o") or 0
    try:
        return round(float(value), 2)
    except Exception:
        return 0.0


def get_qty(product: dict[str, Any]) -> int:
    value = product.get("stock") or 0
    try:
        return max(0, int(round(float(value))))
    except Exception:
        return 0


def build_parent_path(product: dict[str, Any], default_parent: str) -> str:
    path = product.get("category_path") or []
    if isinstance(path, list):
        normalized = [str(item).strip() for item in path if str(item).strip()]
        if normalized:
            return " / ".join(normalized)
    return default_parent.strip()


def build_presence(qty: int, env: dict[str, str]) -> str:
    in_stock = env.get("HOROSHOP_PRESENCE_IN_STOCK", "у наявності").strip() or "у наявності"
    out_of_stock = env.get("HOROSHOP_PRESENCE_OUT_OF_STOCK", "немає в наявності").strip() or "немає в наявності"
    return in_stock if qty > 0 else out_of_stock


def build_product_payload(
    product: dict[str, Any],
    env: dict[str, str],
    meta: dict | None = None,
    skip_meta: bool = False,
) -> dict[str, Any]:
    kod = str(product.get("kod") or "").strip()
    qty = get_qty(product)
    price = get_price(product)
    currency = env.get("HOROSHOP_CURRENCY", "UAH").strip() or "UAH"
    default_parent = env.get("HOROSHOP_DEFAULT_PARENT", "").strip()
    stock_mode = (env.get("HOROSHOP_STOCK_MODE", "presence").strip() or "presence").lower()

    # Назва та бренд — з meta_store (AI-нормалізовані) або з УкрСкладу
    m = (meta or {}) if not skip_meta else {}
    name = (m.get("display_name") or "").strip() or str(product.get("name") or kod).strip()
    brand = (m.get("brand") or "").strip() or str(product.get("proizv") or "").strip()

    payload: dict[str, Any] = {
        "article": kod,
        "price": price,
        "currency": currency,
        "display_in_showcase": 1 if as_bool(str(product.get("visible", 1)), True) else 0,
        "title": name,
        "parent_article": kod,
    }

    parent_path = build_parent_path(product, default_parent)
    if parent_path:
        payload["parent"] = parent_path

    if brand:
        payload["brand"] = brand

    # Опис з meta_store (AI / шаблонний) або з УкрСкладу як fallback
    if not skip_meta and m:
        desc_html = (m.get("description_html") or "").strip()
        if not desc_html:
            # Шаблонний опис із feed_content
            try:
                import sys
                sys.path.insert(0, str(ROOT / "src"))
                from feed_content import resolve_description_html
                name_raw = str(product.get("name") or "").strip()
                desc_html = resolve_description_html(m, name_raw)
            except Exception:
                pass
        if desc_html:
            payload["description"] = desc_html
    else:
        description = str(product.get("descr_big") or "").strip()
        if description:
            payload["description"] = description

    # Характеристики (properties) з meta_store
    if not skip_meta and m:
        props = collect_properties(m)
        if props:
            payload["properties"] = props

    # Фото з meta_store
    if not skip_meta and m:
        pics = [p for p in (m.get("pictures") or []) if p]
        if pics:
            payload["images"] = pics

    if stock_mode == "residues":
        warehouse = env.get("HOROSHOP_WAREHOUSE", "").strip()
        if not warehouse:
            raise RuntimeError("Для HOROSHOP_STOCK_MODE=residues потрібно задати HOROSHOP_WAREHOUSE в .env")
        payload["residues"] = [{"warehouse": warehouse, "quantity": qty}]
    else:
        payload["presence"] = build_presence(qty, env)

    return payload


def chunked(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def canonical_to_api_payload(item: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    stock_mode = (env.get("HOROSHOP_STOCK_MODE", "presence").strip() or "presence").lower()
    payload: dict[str, Any] = {
        "article": item["article"],
        "price": float(item.get("price") or 0),
        "currency": env.get("HOROSHOP_CURRENCY", item.get("currency", "UAH")).strip() or "UAH",
        "display_in_showcase": int(item.get("display_in_showcase", 1)),
        "title": item["title"],
        "parent_article": item["article"],
    }
    if item.get("parent"):
        payload["parent"] = item["parent"]
    if item.get("brand"):
        payload["brand"] = item["brand"]
    if item.get("description"):
        payload["description"] = item["description"]
    if item.get("params"):
        payload["properties"] = [{"name": p["name"], "value": p["value"]} for p in item["params"]]
    if item.get("images"):
        payload["images"] = list(item["images"])

    qty = int(item.get("quantity") or 0)
    if stock_mode == "residues":
        warehouse = env.get("HOROSHOP_WAREHOUSE", "").strip()
        if not warehouse:
            raise RuntimeError("Для HOROSHOP_STOCK_MODE=residues потрібно задати HOROSHOP_WAREHOUSE в .env")
        payload["residues"] = [{"warehouse": warehouse, "quantity": qty}]
    else:
        payload["presence"] = build_presence(qty, env)
    return payload


def summarize_logs(logs: list[Any]) -> tuple[int, list[str]]:
    errors = 0
    messages: list[str] = []
    for entry in logs[:10]:
        if isinstance(entry, dict):
            code = entry.get("code", "?")
            message = str(entry.get("message") or "").strip()
            if message:
                messages.append(f"{code}: {message}")
                errors += 1
        else:
            messages.append(str(entry))
            errors += 1
    return errors, messages


def sync(
    rebuild_map: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
    batch_size: int = 100,
    skip_meta: bool = False,
) -> dict[str, Any]:
    del rebuild_map  # legacy arg for run_pipeline compatibility

    env = load_env()
    base_url = get_base_url(env)
    hs_login = env.get("HOROSHOP_LOGIN", "").strip()
    hs_pass = env.get("HOROSHOP_PASS", "").strip()

    from horoshop_catalog import build_canonical_products

    canonical_products = build_canonical_products(limit=limit)
    if skip_meta:
        for item in canonical_products:
            item.pop("description", None)
            item["params"] = []
            item["images"] = []

    prepared = [canonical_to_api_payload(item, env) for item in canonical_products]
    batches = chunked(prepared, max(1, batch_size))

    stats: dict[str, Any] = {
        "base_url": base_url,
        "stock_mode": (env.get("HOROSHOP_STOCK_MODE", "presence").strip() or "presence").lower(),
        "total": len(prepared),
        "batches": len(batches),
        "updated": 0,
        "errors": 0,
        "dry_run": dry_run,
    }

    if dry_run:
        preview = prepared[:3]
        print(f"[dry-run] Horoshop sync: {len(prepared)} товарів, {len(batches)} батч(ів)")
        for item in preview:
            print(json.dumps(item, ensure_ascii=False))
        if len(prepared) > len(preview):
            print(f"... ще {len(prepared) - len(preview)} товарів")
        return stats

    if not hs_login or not hs_pass:
        raise RuntimeError(f"HOROSHOP_LOGIN / HOROSHOP_PASS не задані в .env ({ENV_FILE})")

    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync/1.0"

    token = auth(session, base_url, hs_login, hs_pass)
    print(f"Авторизація Horoshop OK, батчів: {len(batches)}")

    for index, batch in enumerate(batches, 1):
        payload = {"token": token, "products": batch}
        data = api_post(session, f"{base_url}/api/catalog/import/", payload)
        status = str(data.get("status") or "").upper()
        print(f"  batch {index}/{len(batches)} -> status={status}, items={len(batch)}")

        if status == "OK":
            stats["updated"] += len(batch)
            continue

        logs = ((data.get("response") or {}).get("log")) if isinstance(data.get("response"), dict) else None
        batch_errors, messages = summarize_logs(logs or [])
        stats["errors"] += max(batch_errors, 1)
        stats["updated"] += max(0, len(batch) - batch_errors)
        if messages:
            for message in messages:
                print(f"    {message}")
        else:
            print(f"    {json.dumps(data, ensure_ascii=False)}")

        if status not in {"WARNING", "OK"}:
            raise RuntimeError(f"Horoshop import завершився зі статусом {status}: {json.dumps(data, ensure_ascii=False)}")

    print(f"Готово: оновлено={stats['updated']} помилок={stats['errors']}")
    return stats


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).parent))

    ap = argparse.ArgumentParser(description="Синхронізує товари з УкрСкладу в Horoshop")
    ap.add_argument("--dry-run", action="store_true", help="Показати payload без реального імпорту")
    ap.add_argument("--limit", type=int, default=None, help="Обмежити кількість товарів для тесту")
    ap.add_argument("--batch-size", type=int, default=100, help="Розмір батчу для catalog/import")
    ap.add_argument("--skip-meta", action="store_true", help="Тільки ціни/залишки, без AI-описів та характеристик")
    args = ap.parse_args()
    sync(dry_run=args.dry_run, limit=args.limit, batch_size=args.batch_size, skip_meta=args.skip_meta)
