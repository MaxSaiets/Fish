"""
Синхронізація товарів з products.json -> Horoshop через офіційний API.

Логіка:
  1. Читає HOROSHOP_* з .env
  2. Отримує token через /api/auth/
  3. Готує payload для /api/catalog/import/
  4. Батчами оновлює ціну, залишок і базові дані товару за article
  5. За потреби може створити відсутній товар, якщо є title + parent

Запуск:
  py src/horoshop_sync.py
  py src/horoshop_sync.py --dry-run
  py src/horoshop_sync.py --limit 10
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).parent.parent
PRODUCTS_JSON = ROOT / "data" / "products.json"
ENV_FILE = ROOT / ".env"
DEFAULT_DOMAIN = "shop645299.horoshop.ua"
PLACEHOLDER_NAMES = {"Повна назва товару", "test", "tetg", "Мій товар"}
PLACEHOLDER_CATEGORIES = {"Ваш тип товарів чи послуг", "Ваша група товарів чи послуг", "Нова група"}


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


def build_product_payload(product: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    kod = str(product.get("kod") or "").strip()
    name = str(product.get("name") or kod).strip()
    brand = str(product.get("proizv") or "").strip()
    description = str(product.get("descr_big") or "").strip()
    qty = get_qty(product)
    price = get_price(product)
    currency = env.get("HOROSHOP_CURRENCY", "UAH").strip() or "UAH"
    default_parent = env.get("HOROSHOP_DEFAULT_PARENT", "").strip()
    stock_mode = (env.get("HOROSHOP_STOCK_MODE", "presence").strip() or "presence").lower()

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
    if description:
        payload["description"] = description

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
) -> dict[str, Any]:
    del rebuild_map  # legacy arg for run_pipeline compatibility

    env = load_env()
    base_url = get_base_url(env)
    hs_login = env.get("HOROSHOP_LOGIN", "").strip()
    hs_pass = env.get("HOROSHOP_PASS", "").strip()

    products = load_products(limit=limit)
    prepared = [build_product_payload(product, env) for product in products]
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
    args = ap.parse_args()
    sync(dry_run=args.dry_run, limit=args.limit, batch_size=args.batch_size)
