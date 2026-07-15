"""
Бекенд Telegram-бота: доступ до каталогу (локально) + live Horoshop (лічильник, запис ціни/наявності).

Дані:
  - Каталог (stats/search/recent/product) — з локального products.json через build_canonical_products (швидко, без запитів).
  - Live-лічильник товарів — 1 запит до datagrid-пейджера Horoshop.
  - Запис ціни/наявності — form-канал (GET edit.php → POST save.php), безпечно (зберігає всі поля).

Створені товари (edit.php=503) для запису недоступні — повертається зрозуміла помилка.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
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

ID_MAP = ROOT / "data" / "article_id_full.json"
PROGRESS = ROOT / "data" / "bulk_char_progress.json"


# ---------- Каталог (локально) ----------

def _catalog():
    from horoshop_catalog import build_canonical_products
    return build_canonical_products()


def _by_article():
    return {str(p["article"]).strip(): p for p in _catalog()}


def _qty(p) -> int:
    try:
        return int(p.get("quantity") or 0)
    except Exception:
        return 0


def load_id_map() -> dict:
    if ID_MAP.exists():
        return json.loads(ID_MAP.read_text(encoding="utf-8"))
    return {}


def catalog_stats() -> dict:
    prods = _catalog()
    from collections import Counter
    fam = Counter(p.get("family") for p in prods)
    cats = Counter(p.get("parent") for p in prods)
    instock = sum(1 for p in prods if _qty(p) > 0)
    prices = [float(p.get("price") or 0) for p in prods if float(p.get("price") or 0) > 0]
    done = 0
    if PROGRESS.exists():
        try:
            done = len(json.loads(PROGRESS.read_text(encoding="utf-8")))
        except Exception:
            done = 0
    return {
        "total": len(prods),
        "instock": instock,
        "outofstock": len(prods) - instock,
        "categories": len(cats),
        "families": len(fam),
        "top_families": fam.most_common(8),
        "top_categories": cats.most_common(8),
        "avg_price": round(sum(prices) / len(prices), 2) if prices else 0,
        "chars_uploaded": done,
    }


def recent_products(n: int = 10) -> list:
    """Останні додані = найбільші внутрішні id Horoshop."""
    id_map = load_id_map()
    by_art = _by_article()
    ranked = sorted(
        ((a, int(i)) for a, i in id_map.items() if str(i).isdigit()),
        key=lambda kv: -kv[1],
    )
    out = []
    for art, iid in ranked[:n]:
        p = by_art.get(art)
        out.append({
            "article": art,
            "id": iid,
            "title": (p or {}).get("title", "(нема в базі)"),
            "price": (p or {}).get("price"),
            "qty": _qty(p) if p else None,
        })
    return out


def search_products(query: str, limit: int = 12) -> list:
    q = query.strip().lower()
    if not q:
        return []
    res = []
    for p in _catalog():
        art = str(p["article"]).strip()
        title = str(p.get("title") or "")
        if q in art.lower() or q in title.lower():
            res.append(p)
        if len(res) >= limit * 3:
            break
    res.sort(key=lambda p: (0 if q == str(p["article"]).strip().lower() else 1, len(str(p.get("title") or ""))))
    return res[:limit]


def product_detail(article: str) -> dict | None:
    p = _by_article().get(str(article).strip())
    if not p:
        return None
    id_map = load_id_map()
    return {
        "article": str(p["article"]).strip(),
        "id": id_map.get(str(p["article"]).strip()),
        "title": p.get("title"),
        "price": p.get("price"),
        "currency": p.get("currency"),
        "qty": _qty(p),
        "family": p.get("family"),
        "brand": p.get("brand"),
        "category": p.get("parent"),
        "params": p.get("params") or [],
        "images": len(p.get("images") or []),
    }


def lowstock(threshold: int = 3) -> list:
    out = [p for p in _catalog() if 0 < _qty(p) <= threshold]
    out.sort(key=_qty)
    return [{"article": str(p["article"]).strip(), "title": p.get("title"), "qty": _qty(p)} for p in out]


# ---------- Live Horoshop ----------

def _session():
    env = load_env()
    base = get_base_url(env)
    s = requests.Session()
    s.headers["User-Agent"] = "fish-tg-bot/1.0"
    auth(s, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])
    return s, base, env


def live_product_count() -> int | None:
    """Реальна кількість товарів із пейджера datagrid (1 запит)."""
    try:
        s, base, _ = _session()
        r = s.get(f"{base}/adminLegacy/data.php?parent=97&handler=17&showPages",
                  timeout=40, verify=False)
        m = re.search(r"(?:з|из|of)\s+([\d\s]{2,10})", re.sub("<[^>]+>", " ", r.text))
        if m:
            return int(re.sub(r"\s", "", m.group(1)))
    except Exception:
        return None
    return None


def run_stock_sync() -> str:
    """UkrSklad → Horoshop: ціни/наявність (1 pricelist-аплоад, ~6-8 запитів). Безпечно."""
    import subprocess
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "src" / "sync_stock_playwright.py")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
        out = (r.stdout or "") + (r.stderr or "")
        m = re.search(r"Обновлено[:\s]+(\d+)", out) or re.search(r'"updated":\s*(\d+)', out)
        upd = m.group(1) if m else "?"
        ok = "status\": \"ok" in out or "Статус: ok" in out
        return (f"✅ Синхронізація цін/наявності завершена.\nОновлено товарів: <b>{upd}</b>."
                if ok or upd != "?" else f"⚠️ Синхронізація завершилась із невизначеним статусом.\n{out[-200:]}")
    except subprocess.TimeoutExpired:
        return "⚠️ Синхронізація триває довше очікуваного (перевищено таймаут). Перевір лог."
    except Exception as exc:
        return f"❌ Помилка синхронізації: {str(exc)[:200]}"


def run_order_sync() -> str:
    """Horoshop замовлення → UkrSklad: списання залишків + видаткові накладні."""
    import subprocess
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "src" / "sync_orders.py")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
        out = (r.stdout or "") + (r.stderr or "")
        proc = len(re.findall(r"OK VNAKL", out))
        newo = re.search(r"(?:нових замовлень|new orders)[:\s]+(\d+)", out)
        return (f"✅ Замовлення оброблено.\nСписано в УкрСкладі накладних: <b>{proc}</b>."
                if proc else f"ℹ️ Нових замовлень для списання не знайдено.\n{out[-200:]}")
    except subprocess.TimeoutExpired:
        return "⚠️ Обробка замовлень триває довше очікуваного."
    except Exception as exc:
        return f"❌ Помилка обробки замовлень: {str(exc)[:200]}"


def set_field(article: str, field: str, value) -> tuple[bool, str]:
    """Змінює ОДНЕ поле товару (price/price_old/presence/quantity) через форму,
    зберігаючи всі інші. field: 'price' | 'presence' | 'quantity'."""
    id_map = load_id_map()
    pid = id_map.get(str(article).strip())
    if not pid:
        return False, f"Артикул {article} не знайдено в мапі id."
    field_map = {
        "price": "modifications[0][price]",
        "quantity": "modifications[0][quantity]",
        "presence": "modifications[0][presence]",
    }
    if field not in field_map:
        return False, f"Невідоме поле {field}."
    try:
        s, base, _ = _session()
        url = (f"{base}/adminLegacy/edit.php?id={pid}&parent=97"
               f"&action=edit&handler=381&checkcode=yamete_kudasai")
        r = s.get(url, timeout=60, verify=False)
        if r.status_code == 503 or "modifications[0]" not in r.text:
            return False, ("Товар недоступний для редагування через стару форму (503 — "
                           "створений у новому редакторі). Зміни його вручну в адмінці.")
        p = LegacyFormParser()
        p.feed(r.text)
        f = dict(p.fields)
        if str(f.get("modifications[0][article]", "")).strip() != str(article).strip():
            return False, "Артикул форми не збігся (безпека) — скасовано."
        payload = {k: v for k, v in f.items() if str(v) != ""}
        payload[field_map[field]] = str(value)
        payload.update({
            "checkcode": "yamete_kudasai", "id": pid, "handler": "381",
            "handlertable": "h_product_characteristics", "back": "index.php",
        })
        resp = post_form(s, f"{base}/adminLegacy/save.php", payload, url)
        resp.raise_for_status()
        if "HTTP_ERROR" in resp.text[:400]:
            return False, "Сервер повернув помилку збереження."
        return True, f"OK: {field}={value} для {article} (id {pid})."
    except Exception as exc:
        return False, f"Помилка: {str(exc)[:160]}"
