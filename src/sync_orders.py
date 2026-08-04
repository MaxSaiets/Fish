"""
sync_orders.py — автоматична синхронізація замовлень Horoshop → УкрСклад7

При кожному запуску:
  1. Playwright скрапить нові замовлення з Horoshop admin
  2. Для кожного нового замовлення:
     a. Створює видаткову накладну (VNAKL + VNAKL_) в УкрСклад
     b. Зменшує залишок (TOVAR_ZAL.KOLVO) на куплену кількість
  3. Зберігає список оброблених замовлень → data/processed_orders.json

Запуск:
  cd D:\\FISH\\fish-sync
  python src\\sync_orders.py                      # реальна синхронізація
  python src\\sync_orders.py --dry-run             # тест без запису в БД
  python src\\sync_orders.py --headful             # браузер видимий (debug)
  python src\\sync_orders.py --since 2026-06-01    # тільки замовлення після дати

Логи: D:\\FISH\\fish-sync\\logs\\orders_YYYYMMDD_HHMMSS.log
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"
PROCESSED_FILE = DATA_DIR / "processed_orders.json"

sys.path.insert(0, str(ROOT / "src"))


# ---------------------------------------------------------------------------
# 1. ЗЧИТУЄМО ОБРОБЛЕНІ ЗАМОВЛЕННЯ (щоб не дублювати)
# ---------------------------------------------------------------------------

def load_processed() -> set[str]:
    if PROCESSED_FILE.exists():
        return set(json.loads(PROCESSED_FILE.read_text(encoding="utf-8")))
    return set()


def save_processed(processed: set[str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_FILE.write_text(
        json.dumps(sorted(processed), ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# 2. PLAYWRIGHT — ЗЧИТУЄМО ЗАМОВЛЕННЯ З HOROSHOP
# ---------------------------------------------------------------------------

def fetch_orders_playwright(
    base_url: str,
    login: str,
    password: str,
    since_date: datetime | None = None,
    headful: bool = False,
) -> list[dict]:
    """
    Повертає список замовлень.
    Horoshop рендерить рядки через datagrid як <tr id="dataGridRow_N">.
    ID N — це внутрішній ID замовлення (використовується в ?print&id=N).
    """
    from playwright.sync_api import sync_playwright

    orders = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headful)
        context = browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126",
        )
        page = context.new_page()

        # Логін
        page.goto(f"{base_url}/", wait_until="domcontentloaded", timeout=15000)
        result = page.evaluate(
            """async ([url, login, password]) => {
                const r = await fetch(url + '/core-api/admin/security/login', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({login, password})
                });
                return {status: r.status};
            }""",
            [base_url, login, password],
        )
        if result.get("status") != 200:
            raise RuntimeError(f"Login failed: {result}")
        print(f"  Login OK")

        # Завантажуємо сторінку замовлень
        orders_url = f"{base_url}/adminLegacy/handlers/orders.php"
        page.goto(orders_url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)

        # Знаходимо datagridHandlerId (для логу)
        hid = page.evaluate("""
            (function() {
                var scripts = document.querySelectorAll('script');
                for(var i=0; i<scripts.length; i++) {
                    var m = scripts[i].innerText.match(/datagridHandlerId\\s*=\\s*(\\d+)/);
                    if(m) return m[1];
                }
                return null;
            })()
        """)
        print(f"  datagridHandlerId: {hid}")

        # Метод: DOM — після networkidle datagrid вже відрендерено
        # Horoshop рендерить рядки як <tr id="dataGridRow_N"> де N — internal order ID
        html = page.content()
        order_ids = list(dict.fromkeys(re.findall(r'id="dataGridRow_(\d+)"', html)))

        if order_ids:
            print(f"  Знайдено ID у DOM (dataGridRow): {order_ids}")
        else:
            # Fallback: стандартні посилання
            order_ids = list(dict.fromkeys(re.findall(r'orders\.php\?(?:view&)?id=(\d+)', html)))
            if order_ids:
                print(f"  Знайдено ID у DOM (links): {order_ids}")
            else:
                print("  Замовлень у DOM не знайдено")

        # Для кожного замовлення завантажуємо деталі через print-view
        for oid in order_ids:
            try:
                order = fetch_order_details(page, base_url, oid, since_date)
                if order:
                    orders.append(order)
            except Exception as e:
                print(f"  [WARN] order {oid}: {e}")

        browser.close()

    return orders


def fetch_order_details(
    page,
    base_url: str,
    order_id: str,
    since_date: datetime | None,
) -> dict | None:
    """
    Завантажує деталі одного замовлення через print-view.

    Horoshop рендерить товари у форматі:
        <div class="col-1">Назва товару(артикул)</div>
        <div class="col-2">кількість</div>
        <div class="col-3">ціна грн</div>
    """
    print_url = f"{base_url}/adminLegacy/handlers/orders.php?print&id={order_id}"
    page.goto(print_url, wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(1000)

    html = page.content()
    text = page.inner_text("body")

    # -- Дата замовлення -----------------------------------------------------
    order_date = None
    # "2026-06-08 10:56:59"
    dm = re.search(r"(\d{4})-(\d{2})-(\d{2})\s+\d{2}:\d{2}", text)
    if dm:
        try:
            order_date = datetime(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
        except ValueError:
            pass
    if not order_date:
        dm2 = re.search(r"(\d{2})[./\-](\d{2})[./\-](\d{4})", text)
        if dm2:
            try:
                order_date = datetime(int(dm2.group(3)), int(dm2.group(2)), int(dm2.group(1)))
            except ValueError:
                pass

    if since_date and order_date and order_date < since_date:
        return None

    # -- Телефон та ім'я клієнта --------------------------------------------
    phone = ""
    customer = ""

    phone_match = re.search(r"(\+?3?8?\s*\(?0\d{2}\)?\s*[\d\s\-]{7,})", text)
    if phone_match:
        phone = re.sub(r"\s+", "", phone_match.group(1)).strip()

    # Ім'я клієнта — рядок між часом HH:MM і телефоном у тексті сторінки
    cust_match = re.search(r"\d{1,2}:\d{2}\s*\n+\s*(.{2,60}?)\s*\n+\s*\+?[\d(]", text)
    if cust_match:
        cand = cust_match.group(1).strip()
        if not re.match(r"^\d+$", cand):
            customer = cand

    # -- Сума замовлення ----------------------------------------------------
    total = 0.0
    total_match = re.search(r"([\d]+(?:[.,]\d+)?)\s*грн\b", text)
    if total_match:
        try:
            total = float(total_match.group(1).replace(",", "."))
        except ValueError:
            pass

    # -- Товари: col-1 / col-2 / col-3 -------------------------------------
    # Horoshop: <div class="col-1">Назва(артикул)</div>
    #           <div class="col-2">1 </div>
    #           <div class="col-3">850 грн</div>
    items = []

    col1_els = page.query_selector_all("div.col-1")
    col2_els = page.query_selector_all("div.col-2")
    col3_els = page.query_selector_all("div.col-3")

    for i in range(min(len(col1_els), len(col2_els), len(col3_els))):
        c1 = col1_els[i].inner_text().strip()
        c2 = col2_els[i].inner_text().strip()
        c3 = col3_els[i].inner_text().strip()
        if not c1:
            continue

        # "Котушка с байтраннером Legend Fishing Gear - KTR 5000A(1432)"
        art_m = re.search(r"\(([A-Za-z0-9\-_\.# ]{1,30})\)\s*$", c1)
        article = art_m.group(1).strip() if art_m else ""
        name = c1[: art_m.start()].strip() if art_m else c1

        qty_m = re.search(r"([\d]+(?:[.,]\d+)?)", c2)
        qty = float(qty_m.group(1).replace(",", ".")) if qty_m else 1.0

        price_s = re.sub(r"[^\d.,]", "", c3).replace(",", ".")
        try:
            price = float(price_s) if price_s else 0.0
        except ValueError:
            price = 0.0

        # Пропускаємо підсумкові рядки Horoshop (без артикулу і з назвою-підсумком)
        SUMMARY_KEYWORDS = ("разом", "доставка", "всього", "комісія", "знижка",
                            "total", "delivery", "discount", "fee")
        is_summary = not article and any(kw in name.lower() for kw in SUMMARY_KEYWORDS)
        if (name or article) and not is_summary:
            items.append({"article": article, "name": name[:100], "qty": qty, "price": price})

    # Fallback: regex по HTML якщо query_selector не знайшов col-1/col-2/col-3
    if not items:
        row_re = re.compile(
            r'<div class="col-1">(.*?)</div>.*?'
            r'<div class="col-2">(.*?)</div>.*?'
            r'<div class="col-3">(.*?)</div>',
            re.DOTALL | re.IGNORECASE,
        )
        for m in row_re.finditer(html):
            c1 = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            c2 = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            c3 = re.sub(r"<[^>]+>", "", m.group(3)).strip()
            if not c1:
                continue
            art_m = re.search(r"\(([A-Za-z0-9\-_\.# ]{1,30})\)\s*$", c1)
            article = art_m.group(1).strip() if art_m else ""
            name = c1[: art_m.start()].strip() if art_m else c1
            qty_m = re.search(r"([\d]+(?:[.,]\d+)?)", c2)
            qty = float(qty_m.group(1).replace(",", ".")) if qty_m else 1.0
            price_s = re.sub(r"[^\d.,]", "", c3).replace(",", ".")
            try:
                price = float(price_s) if price_s else 0.0
            except ValueError:
                price = 0.0
            if name or article:
                items.append({"article": article, "name": name[:100], "qty": qty, "price": price})

    if not items:
        print(f"  [WARN] order {order_id}: no items found ({print_url})")

    return {
        "horoshop_id": order_id,
        "date": order_date.strftime("%Y-%m-%d") if order_date else datetime.now().strftime("%Y-%m-%d"),
        "customer": customer or f"Horoshop #{order_id}",
        "phone": phone,
        "total": total,
        "items": items,
        "source_url": print_url,
    }


# ---------------------------------------------------------------------------
# 3. УКРСКЛАД — ЗАПИСУЄМО ВИДАТКОВУ НАКЛАДНУ
# ---------------------------------------------------------------------------

def write_sale_to_ukrsklad(order: dict, dry_run: bool = False) -> dict:
    """
    Створює видаткову накладну (VNAKL + VNAKL_) в УкрСклад і зменшує TOVAR_ZAL.
    Повертає {"status": "ok"|"skip"|"error", "vnakl_num": N, "items_written": N}
    """
    import os as _os
    from ukrsklad import LIVE_DB, FBCLIENT, USER, PASSWORD, CHARSET
    _os.environ["PATH"] = str(FBCLIENT.parent) + _os.pathsep + _os.environ.get("PATH", "")
    import fdb

    items = order.get("items", [])
    if not items:
        return {"status": "skip", "reason": "no_items"}

    if dry_run:
        print(f"  [dry-run] invoice for '{order['customer']}', {len(items)} items")
        for item in items:
            print(f"    article={item.get('article')} | qty={item.get('qty')} | price={item.get('price')} | {item.get('name','')[:50]}")
        return {"status": "dry_run", "items": len(items)}

    conn = fdb.connect(
        database=str(LIVE_DB),
        user=USER,
        password=PASSWORD,
        charset=CHARSET,
        fb_library_name=str(FBCLIENT),
    )
    cur = conn.cursor()

    try:
        # Визначаємо наступний NUM для VNAKL
        cur.execute("SELECT MAX(NUM) FROM VNAKL")
        row = cur.fetchone()
        next_vnakl_num = (row[0] or 0) + 1

        order_date = (
            datetime.strptime(order["date"], "%Y-%m-%d")
            if isinstance(order["date"], str)
            else order["date"]
        )
        client_name = (order.get("customer") or f"Horoshop #{order['horoshop_id']}")[:100]
        total = float(
            order.get("total") or sum(i.get("price", 0) * i.get("qty", 1) for i in items)
        )
        comment = f"Horoshop #{order['horoshop_id']}"

        # Вставляємо VNAKL (шапка накладної)
        cur.execute(
            """
            INSERT INTO VNAKL (
                NUM, FIRMA_ID, NU, DATE_DOK, CLIENT, CLIENT_ID,
                CENA, CENA_PDV, CENA_ZNIG,
                SKLAD_ID, CURR_TYPE, PDV, IS_MOVE,
                DOC_MARK_TYPE, DOC_USER_ID, DOC_LAST_USER_ID,
                DOC_DESCR, PDV_TYPE,
                CENA_TOV_TRANS, CURR_CENA_TOV_TRANS,
                ZNIG_PROC, AKCIZ, CURR_AKCIZ,
                SUMA_FULL, CURR_SUMA_FULL,
                CENA_ZNIG_FULL, CURR_CENA_ZNIG_FULL,
                CENA_FROM_CLIENT2, RESP_CLIENT_ID
            ) VALUES (
                ?, 1, ?, ?, ?, -20,
                ?, ?, 0,
                1, 0, 0.0, 1,
                0, 1, -1,
                ?, 1,
                0, 0,
                0, 0, 0,
                0, 0,
                0, 0,
                0, -1
            )
            """,
            (
                next_vnakl_num,
                str(next_vnakl_num),
                order_date,
                client_name,
                total,
                total,
                comment,
            ),
        )

        # Вставляємо рядки VNAKL_ і оновлюємо TOVAR_ZAL
        items_written = 0
        items_not_found = []

        for item in items:
            article = (item.get("article") or "").strip()
            name = (item.get("name") or article or "Tovar")[:100]
            qty = float(item.get("qty") or 1)
            price = float(item.get("price") or 0)
            suma = round(qty * price, 2)

            # Знаходимо TOVAR_ID за артикулом (KOD)
            tovar_id = None
            if article:
                cur.execute(
                    "SELECT NUM FROM TOVAR_NAME WHERE KOD = ? AND VISIBLE = 1 ROWS 1",
                    (article,),
                )
                r = cur.fetchone()
                if r:
                    tovar_id = r[0]

            # Fallback: шукаємо за назвою
            if not tovar_id and name:
                cur.execute(
                    "SELECT NUM FROM TOVAR_NAME WHERE UPPER(NAME) CONTAINING UPPER(?) AND VISIBLE=1 ROWS 1",
                    (name[:30],),
                )
                r = cur.fetchone()
                if r:
                    tovar_id = r[0]

            if not tovar_id:
                items_not_found.append(article or name)

            # Визначаємо наступний NUM для VNAKL_
            cur.execute("SELECT MAX(NUM) FROM VNAKL_")
            r2 = cur.fetchone()
            next_line_num = (r2[0] or 0) + 1

            cur.execute(
                """
                INSERT INTO VNAKL_ (
                    NUM, PID, TOV_NAME, TOVAR_ID,
                    TOV_KOLVO, TOV_CENA, TOV_CENA_PDV,
                    TOV_SUMA, CURR_TOV_SUMA,
                    TOV_ED, SKLAD_ID, IS_PDV,
                    COMPL_ID, IS_COMPL, COMPL_IS_CONST,
                    TOV_SUMA_ZNIG, CURR_TOV_SUMA_ZNIG,
                    TOV_CENA_FULL, CURR_TOV_CENA_FULL,
                    TOV_SUMA_FULL, CURR_TOV_SUMA_FULL,
                    TOV_PDV, CURR_TOV_PDV,
                    TOV_AKCIZ, CURR_TOV_AKCIZ,
                    TOV_SUMA_ZNIG_FULL, CURR_TOV_SUMA_ZNIG_FULL
                ) VALUES (
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    'sht', 1, -1,
                    0, 0, 0,
                    0, 0,
                    ?, ?,
                    ?, ?,
                    0, 0,
                    0, 0,
                    0, 0
                )
                """,
                (
                    next_line_num,
                    next_vnakl_num,
                    name,
                    tovar_id,
                    qty,
                    price,
                    price,
                    suma,
                    suma,
                    price,
                    price,
                    suma,
                    suma,
                ),
            )

            # Зменшуємо TOVAR_ZAL.KOLVO якщо знайдений товар
            if tovar_id:
                cur.execute(
                    "UPDATE TOVAR_ZAL SET KOLVO = KOLVO - ? WHERE TOVAR_ID = ? AND SKLAD_ID = 1 AND VISIBLE = 1",
                    (qty, tovar_id),
                )
                if cur.rowcount == 0:
                    print(f"    [WARN] TOVAR_ZAL not found for TOVAR_ID={tovar_id}")

            items_written += 1

        conn.commit()
        print(f"  OK VNAKL #{next_vnakl_num} | {items_written} items | client: {client_name}")
        if items_not_found:
            print(f"    Not found in UkrSklad: {items_not_found}")

        return {
            "status": "ok",
            "vnakl_num": next_vnakl_num,
            "items_written": items_written,
            "items_not_found": items_not_found,
        }

    except Exception as exc:
        conn.rollback()
        raise exc
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 4. MAIN
# ---------------------------------------------------------------------------

def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def send_telegram_notification(text: str, env: dict[str, str]) -> None:
    token = env.get("TELEGRAM_BOT_TOKEN")
    admin_ids_str = env.get("TELEGRAM_ADMIN_IDS")
    if not token or not admin_ids_str:
        return

    import urllib.request
    import urllib.parse

    admin_ids = [aid.strip() for aid in admin_ids_str.split(",") if aid.strip()]
    for aid in admin_ids:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": aid, "text": text, "parse_mode": "HTML"}).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=10) as res:
                pass
        except Exception as e:
            print(f"  [WARN] Failed to send Telegram notification to {aid}: {e}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync orders Horoshop -> UkrSklad")
    ap.add_argument("--dry-run", action="store_true", help="Do not write to DB")
    ap.add_argument("--headful", action="store_true", help="Show browser")
    ap.add_argument("--since", default=None, help="Start date YYYY-MM-DD (default: -7 days)")
    ap.add_argument("--force", action="store_true", help="Process already-processed orders")
    args = ap.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    started = datetime.now()
    report: dict = {"started": started.isoformat(), "orders": []}

    since_date = (
        datetime.strptime(args.since, "%Y-%m-%d")
        if args.since
        else datetime.now() - timedelta(days=7)
    )

    env = load_env()
    base = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    login = env.get("HOROSHOP_LOGIN", "")
    password = env.get("HOROSHOP_PASS", "")

    processed = load_processed()
    print(f"Already processed: {len(processed)}")

    print(f"\n--- Step 1: Fetch orders from Horoshop (since {since_date.strftime('%Y-%m-%d')})...")
    try:
        orders = fetch_orders_playwright(base, login, password, since_date, args.headful)
        print(f"  Found orders: {len(orders)}")
    except Exception as e:
        report["status"] = "error"
        report["error"] = str(e)
        report["traceback"] = traceback.format_exc()
        log_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ERROR] {e}")
        return 1

    new_orders = [o for o in orders if o["horoshop_id"] not in processed or args.force]
    print(f"  New (unprocessed): {len(new_orders)}")

    if not new_orders:
        print("  Nothing new — exit")
        report["status"] = "ok"
        report["new_orders"] = 0
        log_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0

    print(f"\n--- Step 2: Write to UkrSklad...")
    success = 0
    errors = 0

    for order in new_orders:
        print(f"\n  Order #{order['horoshop_id']} | {order['date']} | {order['customer']}")
        try:
            result = write_sale_to_ukrsklad(order, dry_run=args.dry_run)
            order["ukrsklad_result"] = result
            report["orders"].append(order)

            if result["status"] in ("ok", "dry_run"):
                if not args.dry_run:
                    processed.add(order["horoshop_id"])
                success += 1
            else:
                print(f"  [SKIP] {result.get('reason')}")
        except Exception as e:
            errors += 1
            order["ukrsklad_result"] = {"status": "error", "error": str(e)}
            report["orders"].append(order)
            print(f"  [ERROR] {e}")

    if not args.dry_run:
        save_processed(processed)

    if success > 0 and not args.dry_run:
        msg_lines = [f"🛒 <b>Нові замовлення синхронізовано!</b> ({success} шт.)\n"]
        for order in new_orders:
            if order.get("ukrsklad_result", {}).get("status") == "ok":
                items_count = sum(i.get("qty", 1) for i in order.get("items", []))
                msg_lines.append(f"• Замовлення <b>#{order['horoshop_id']}</b>")
                msg_lines.append(f"👤 {order.get('customer', 'Без імені')} | 💰 {order.get('total', 0)} грн")
                msg_lines.append(f"📦 Товарів: {items_count} шт.\n")
        send_telegram_notification("\n".join(msg_lines), env)

    finished = datetime.now()
    report["status"] = "ok" if errors == 0 else "partial"
    report["summary"] = {"success": success, "errors": errors, "total": len(new_orders)}
    report["finished"] = finished.isoformat()
    report["duration_sec"] = round((finished - started).total_seconds(), 1)
    log_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*50}")
    print(f"Done: {success} ok, {errors} errors")
    print(f"Time: {report['duration_sec']}s | Log: {log_path}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
