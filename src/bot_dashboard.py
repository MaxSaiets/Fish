# -*- coding: utf-8 -*-
"""
Реальна бізнес-статистика для Telegram-бота.

Стара статистика показувала внутрішні стани AI-пайплайну
(ai_draft / draft / published), які власниці магазину нічого не кажуть:
  • «Опубліковано» ЗАВЖДИ було 0 — статус 'published' у коді ніколи не ставиться;
  • «Всього в базі 5711» — це parent-моделі, а не товари (їх 8759).

Тут — метрики, за якими реально керують магазином: наявність, фото,
замовлення, продажі, свіжість синхронізації.

Усе читається з локальних файлів (швидко, без запитів до сайту).
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PRODUCTS = ROOT / "data" / "products.json"
SALES = ROOT / "data" / "sales_by_product.json"
PHOTO_AUDIT = ROOT / "data" / "real_photo_audit_v2_full.json"
NOTIFIED_ORDERS = ROOT / "data" / "notified_orders.json"
PROCESSED_ORDERS = ROOT / "data" / "processed_orders.json"
LOGS = ROOT / "logs"


# ─────────────────────────── утиліти ───────────────────────────

def _load(path: Path, default):
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _age(path: Path) -> str:
    """Скільки часу минуло з останньої зміни файлу."""
    if not path.exists():
        return "немає"
    delta = time.time() - path.stat().st_mtime
    if delta < 3600:
        return f"{int(delta // 60)} хв тому"
    if delta < 86400:
        return f"{int(delta // 3600)} год тому"
    return f"{int(delta // 86400)} дн тому"


def _num(n) -> str:
    """1234567 → 1 234 567"""
    return f"{int(n):,}".replace(",", " ")


# ─────────────────────────── метрики ───────────────────────────

def catalog_metrics() -> dict:
    data = _load(PRODUCTS, {})
    products = data.get("products", []) if isinstance(data, dict) else []
    visible = [p for p in products if str(p.get("visible")) == "1"]
    instock = [p for p in visible if float(p.get("stock") or 0) > 0]
    noprice = [p for p in visible if not float(p.get("cena_r") or 0)]
    return {
        "total": len(visible),
        "instock": len(instock),
        "outofstock": len(visible) - len(instock),
        "noprice": len(noprice),
        "updated": _age(PRODUCTS),
    }


def photo_metrics() -> dict:
    audit = _load(PHOTO_AUDIT, [])
    if not isinstance(audit, list) or not audit:
        return {"checked": 0, "real": 0, "placeholder": 0, "pct": 0}
    real = sum(1 for a in audit if a.get("real"))
    return {
        "checked": len(audit),
        "real": real,
        "placeholder": len(audit) - real,
        "pct": round(real * 100 / len(audit), 1),
    }


def orders_metrics() -> dict:
    notified = _load(NOTIFIED_ORDERS, [])
    processed = _load(PROCESSED_ORDERS, [])
    if isinstance(processed, dict):
        processed = list(processed.keys())
    return {
        "notified_total": len(notified) if isinstance(notified, list) else 0,
        "processed_total": len(processed) if isinstance(processed, list) else 0,
        "last_check": _age(NOTIFIED_ORDERS),
    }


def sales_metrics(top_n: int = 5) -> dict:
    sales = _load(SALES, [])
    if not isinstance(sales, list) or not sales:
        return {"positions": 0, "revenue": 0, "top": []}
    revenue = sum(float(s.get("rev") or 0) for s in sales)
    ranked = sorted(sales, key=lambda s: -float(s.get("rev") or 0))[:top_n]
    top = [
        {
            "name": (s.get("name") or "?")[:38],
            "kod": s.get("kod") or "",
            "rev": float(s.get("rev") or 0),
            "qty": float(s.get("qty") or 0),
        }
        for s in ranked
    ]
    return {"positions": len(sales), "revenue": revenue, "top": top}


def stale_top_sellers(limit: int = 8) -> list[dict]:
    """Топ-товари за продажами, яких ЗАРАЗ немає в наявності — прямі втрачені гроші."""
    data = _load(PRODUCTS, {})
    products = data.get("products", []) if isinstance(data, dict) else []
    stock_by_kod = {
        str(p.get("kod") or "").strip(): float(p.get("stock") or 0)
        for p in products
        if p.get("kod")
    }
    sales = _load(SALES, [])
    out = []
    for s in sorted(sales, key=lambda x: -float(x.get("rev") or 0)):
        kod = str(s.get("kod") or "").strip()
        if not kod or kod not in stock_by_kod:
            continue
        if stock_by_kod[kod] > 0:
            continue
        out.append(
            {"kod": kod, "name": (s.get("name") or "?")[:38], "rev": float(s.get("rev") or 0)}
        )
        if len(out) >= limit:
            break
    return out


def sync_health() -> dict:
    """Свіжість даних і результат останнього прогону пайплайну."""
    logs = sorted(LOGS.glob("pipeline_*.log"), key=lambda p: p.stat().st_mtime, reverse=True) \
        if LOGS.is_dir() else []
    last_status, last_when = "немає запусків", "—"
    if logs:
        last_when = _age(logs[0])
        try:
            payload = json.loads(logs[0].read_text(encoding="utf-8"))
            last_status = payload.get("status", "?")
        except Exception:
            txt = logs[0].read_text(encoding="utf-8", errors="replace")
            last_status = "ok" if '"status": "ok"' in txt else "невідомо"
    return {
        "products_age": _age(PRODUCTS),
        "pipeline_status": last_status,
        "pipeline_when": last_when,
    }


# ─────────────────────────── рендер ───────────────────────────

def dashboard_html() -> str:
    """Головний екран бота — зрозумілий власниці магазину."""
    cat = catalog_metrics()
    photo = photo_metrics()
    orders = orders_metrics()
    sales = sales_metrics()
    health = sync_health()

    instock_pct = round(cat["instock"] * 100 / cat["total"], 1) if cat["total"] else 0

    lines = [
        "📊 <b>СТАН МАГАЗИНУ</b>",
        "",
        "🛒 <b>Замовлення</b>",
        f"   Оброблено всього: <b>{orders['processed_total']}</b>",
        f"   Перевірка нових: {orders['last_check']}",
        "",
        "📦 <b>Каталог</b>",
        f"   Товарів: <b>{_num(cat['total'])}</b>",
        f"   В наявності: <b>{_num(cat['instock'])}</b> ({instock_pct}%)",
        f"   Немає в наявності: {_num(cat['outofstock'])}",
    ]
    if cat["noprice"]:
        lines.append(f"   ⚠️ Без ціни: {cat['noprice']}")

    lines += [
        "",
        "📸 <b>Фото</b>",
        f"   Реальних: <b>{_num(photo['real'])}</b> ({photo['pct']}%)",
        f"   ⚠️ Заглушок: <b>{_num(photo['placeholder'])}</b>",
        "",
        "💰 <b>Продажі за весь час</b>",
        f"   Виручка: <b>{_num(sales['revenue'])} грн</b>",
        f"   Позицій продавалось: {_num(sales['positions'])}",
        "",
        "🔄 <b>Синхронізація</b>",
        f"   Дані з УкрСкладу: {health['products_age']}",
        f"   Останній повний цикл: {health['pipeline_when']} ({health['pipeline_status']})",
    ]
    return "\n".join(lines)


def top_sellers_html(n: int = 5) -> str:
    s = sales_metrics(top_n=n)
    if not s["top"]:
        return "Даних про продажі немає."
    lines = [f"🏆 <b>ТОП-{n} за виручкою (весь час)</b>", ""]
    for i, t in enumerate(s["top"], 1):
        lines.append(f"{i}. <b>{t['name']}</b>")
        lines.append(f"    {_num(t['rev'])} грн · {_num(t['qty'])} шт · арт. {t['kod']}")
    return "\n".join(lines)


def stale_top_html(n: int = 8) -> str:
    rows = stale_top_sellers(n)
    if not rows:
        return "✅ Усі топ-товари в наявності."
    lines = ["⚠️ <b>ТОП-ТОВАРИ, ЯКИХ НЕМАЄ В НАЯВНОСТІ</b>",
             "<i>Продавались добре — зараз нульовий залишок</i>", ""]
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. <b>{r['name']}</b>")
        lines.append(f"    було продано на {_num(r['rev'])} грн · арт. {r['kod']}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(dashboard_html().replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", ""))
    print()
    print(top_sellers_html().replace("<b>", "").replace("</b>", ""))
    print()
    print(stale_top_html().replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", ""))
