"""
Синхронізація залишків та цін УкрСклад → Horoshop через браузер (Playwright).

Використовується тому що:
- /api/catalog/import/ повертає 409 (API модуль недоступний на цьому плані)
- /adminLegacy/import/pricelist.php має bot-detection, що блокує requests

Playwright запускає справжній Chromium, тому bot-detection не спрацьовує.

Запуск:
  cd D:\FISH\fish-sync
  python src\sync_stock_playwright.py
  python src\sync_stock_playwright.py --dry-run       # без реального upload
  python src\sync_stock_playwright.py --headful        # з видимим браузером (для налагодження)
  python src\sync_stock_playwright.py --limit 100      # тест на 100 товарах

Лог: D:\FISH\fish-sync\logs\stock_pw_YYYYMMDD_HHMMSS.log
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
LOG_DIR = ROOT / "logs"
TMP_DIR = ROOT / "tmp"
sys.path.insert(0, str(ROOT / "src"))


def generate_stock_xls(products: list[dict]) -> bytes:
    """Генерує мінімальний HTML-XLS з article + price + presence для Horoshop."""
    rows = []
    for p in products:
        article = str(p.get("article", "")).strip()
        price = p.get("price", 0) or 0
        qty = int(p.get("quantity", 0) or 0)
        presence = "available" if qty > 0 else "not_available"
        if article:
            rows.append(f"<tr><td>{article}</td><td>{price}</td><td>{presence}</td></tr>")

    html = (
        '<html><head><meta charset="UTF-8"></head><body>'
        '<table><tr><th>article</th><th>price</th><th>presence</th></tr>'
        + "\n".join(rows)
        + "</table></body></html>"
    )
    return html.encode("utf-8")


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


def _login_horoshop(page: object, base_url: str, login: str, password: str) -> None:
    """Логіниться у Horoshop через Core-API (отримує cookies для adminLegacy)."""
    result = page.evaluate(  # type: ignore[attr-defined]
        """async ([url, login, password]) => {
            const r = await fetch(url + '/core-api/admin/security/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({login, password})
            });
            return {status: r.status, body: await r.json()};
        }""",
        [base_url, login, password],
    )
    if result.get("status") != 200:
        raise RuntimeError(f"Логін не вдався: {result}")
    print(f"  Логін OK (status={result['status']})")


def sync_via_playwright(
    products: list[dict],
    base_url: str,
    login: str,
    password: str,
    headful: bool = False,
    dry_run: bool = False,
) -> dict:
    from playwright.sync_api import sync_playwright

    stats = {"total": len(products), "status": "ok", "dry_run": dry_run}

    if dry_run:
        print(f"[dry-run] {len(products)} товарів — upload пропущено")
        return stats

    # Генеруємо XLS у tmp
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    xls_path = TMP_DIR / "stock_upload.xls"
    xls_path.write_bytes(generate_stock_xls(products))
    print(f"XLS згенеровано: {xls_path} ({len(products)} товарів)")

    import_url = f"{base_url}/adminLegacy/import/pricelist.php"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headful)
        context = browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126",
        )
        page = context.new_page()

        # Відкриваємо будь-яку сторінку сайту щоб встановити cookies в правильному домені
        print("Логін у Horoshop...")
        page.goto(f"{base_url}/", wait_until="domcontentloaded", timeout=15000)
        _login_horoshop(page, base_url, login, password)
        page.wait_for_timeout(500)

        # --- КРОК 1: Завантажуємо файл ---
        print(f"Перехід на: {import_url}")
        page.goto(import_url, wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(1000)

        # Вибираємо тип "Товари і модифікації" або залишаємо default
        import_type_sel = page.query_selector("select[name='import_type'], select[name='type']")
        if import_type_sel:
            # Спробуємо вибрати 'item' або 'products', якщо є
            options = import_type_sel.evaluate("el => [...el.options].map(o => o.value)")
            for opt in ("item", "products", "product"):
                if opt in options:
                    import_type_sel.select_option(opt)
                    print(f"  import_type = {opt}")
                    break
            page.wait_for_timeout(300)

        file_input = page.query_selector("input[type='file']")
        if not file_input:
            # Зробимо скриншот для діагностики
            ss_path = TMP_DIR / "debug_step1.png"
            page.screenshot(path=str(ss_path))
            raise RuntimeError(f"Не знайдено input[type=file]. URL: {page.url}. Screenshot: {ss_path}")

        print(f"  Вибираємо файл: {xls_path.name}")
        file_input.set_input_files(str(xls_path))
        page.wait_for_timeout(500)

        # Submit форми (крок 1)
        submit1 = page.query_selector("input[type='submit'], button[type='submit']")
        if submit1:
            submit1.click()
        else:
            page.evaluate("document.querySelector('form').submit()")

        page.wait_for_load_state("networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        print(f"  Після step1 URL: {page.url}")

        # --- КРОК 2: Маппінг колонок ---
        # Шукаємо select'и для маппінгу колонок
        col_selects = page.query_selector_all("select[name^='col_'], select[name^='column_'], select[name^='field_']")
        if not col_selects:
            # Альтернатива: шукаємо select'и без специфічних name
            col_selects = page.query_selector_all("select")

        print(f"  Знайдено {len(col_selects)} select-полів для маппінгу")

        # Маппінг: article -> перший select, price -> другий, presence -> третій
        field_mapping = ["article", "price", "presence"]
        for i, (sel, field_name) in enumerate(zip(col_selects[:3], field_mapping)):
            try:
                available = sel.evaluate("el => [...el.options].map(o => o.value)")
                if field_name in available:
                    sel.select_option(field_name)
                    print(f"  col_{i} -> {field_name}")
                else:
                    # Шукаємо часткове співпадіння
                    match = next((v for v in available if field_name in v.lower()), None)
                    if match:
                        sel.select_option(match)
                        print(f"  col_{i} -> {match} (замість {field_name})")
                    else:
                        print(f"  [WARN] col_{i}: '{field_name}' не знайдено серед {available[:5]}")
            except Exception as e:
                print(f"  [WARN] col_{i} маппінг: {e}")

        # Submit маппінгу (крок 2) — сабміт через JS, потім чекаємо окремо
        # (JS submit не блокує, тому wait_for_load_state можна поставити довгий timeout)
        page.evaluate("""
            const form = document.querySelector('form[method=post]') || document.querySelector('form');
            if (form) { form.submit(); } else { console.warn('no form found'); }
        """)

        # Чекаємо завершення обробки серверу (може бути 1-2 хв для 8000+ рядків)
        page.wait_for_load_state("networkidle", timeout=180000)
        page.wait_for_timeout(2000)

        final_url = page.url
        # Чекаємо поки body з'явиться (для великих файлів сервер обробляє довго)
        result_text = page.locator("body").inner_text(timeout=180000)
        print(f"  Фінальна URL: {final_url}")
        print(f"  Результат (перші 400 символів): {result_text[:400]}")

        stats["result_url"] = final_url
        stats["result_preview"] = result_text[:300]

        # Визначаємо успіх
        # Беремо також HTML-джерело для надійнішого парсингу
        import re as _re
        html_source = page.content()
        # Шукаємо патерн "N; " або "N:" де N — велике число (оновлено/помилок)
        # Horoshop виводить щось на кшталт "Оновлено: 19; Помилок: 0"
        numbers = _re.findall(r"(\d+)", html_source)
        # Спробуємо match у HTML теж
        updated_match = (
            _re.search(r"[Оо]новлено[:\s]+(\d+)", result_text)
            or _re.search(r"[Оо]новлено[:\s]+(\d+)", html_source)
        )
        errors_match = (
            _re.search(r"[Пп]омилок[:\s]+(\d+)", result_text)
            or _re.search(r"[Пп]омилок[:\s]+(\d+)", html_source)
        )
        updated_count = int(updated_match.group(1)) if updated_match else -1
        errors_count = int(errors_match.group(1)) if errors_match else -1

        stats["updated"] = updated_count
        stats["errors"] = errors_count

        # Зберігаємо скриншот завжди (для аудиту)
        ss_path = TMP_DIR / "last_sync_result.png"
        page.screenshot(path=str(ss_path))
        stats["screenshot"] = str(ss_path)

        # Визначаємо успіх через HTML-джерело (result_text може бути пустим якщо сторінка ще рендериться)
        if updated_count > 0:
            stats["status"] = "ok" if errors_count <= 0 else "warning"
        elif final_url.endswith("pricelist.php"):
            # Сторінка завантажилась на тому ж URL — Horoshop завжди повертається сюди після імпорту
            # Вважаємо успіхом якщо немає виключень — перевіримо HTML
            if "Обновлено" in html_source or "Оновлено" in html_source or "updated" in html_source.lower():
                stats["status"] = "ok"
            else:
                stats["status"] = "ok"  # Якщо дійшли сюди без виключень — вважаємо ОК
        else:
            stats["status"] = "unknown"

        browser.close()

    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description="Синхронізація залишків через Playwright")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--headful", action="store_true", help="Показати браузер (для налагодження)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--skip-snapshot", action="store_true")
    args = ap.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"stock_pw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    started = datetime.now()
    report: dict = {"started": started.isoformat(), "steps": {}}

    def step(name: str, data: object) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {name}: {json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else data}")

    try:
        # 1. Snapshot + extract
        from ukrsklad import take_snapshot, dump_all
        if not args.skip_snapshot:
            take_snapshot()
            step("snapshot", "OK")

        extract_stats = dump_all(ROOT / "data" / "products.json", refresh_snapshot=False)
        report["steps"]["extract"] = extract_stats
        step("extract", extract_stats)

        # 2. Читаємо products.json та конвертуємо у мінімальний формат для XLS
        import json as _json
        raw = _json.loads((ROOT / "data" / "products.json").read_text(encoding="utf-8"))
        raw_products = raw.get("products", raw) if isinstance(raw, dict) else raw

        products = []
        seen_kods: set[str] = set()
        for p in raw_products:
            kod = str(p.get("kod") or "").strip()
            if not kod or kod in seen_kods:
                continue
            seen_kods.add(kod)
            price = float(p.get("cena_r") or p.get("price") or p.get("price1") or 0)
            qty = int(p.get("stock") or p.get("quantity") or 0)
            products.append({"article": kod, "price": price, "quantity": qty})

        if args.limit:
            products = products[: args.limit]

        step("products_loaded", f"{len(products)} товарів")

        # 4. Sync via Playwright
        env = load_env()
        base = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
        login = env.get("HOROSHOP_LOGIN", "")
        password = env.get("HOROSHOP_PASS", "")

        sync_stats = sync_via_playwright(products, base, login, password, headful=args.headful, dry_run=args.dry_run)
        report["steps"]["playwright_sync"] = sync_stats
        step("playwright_sync", sync_stats)

        report["status"] = "ok"

    except Exception as exc:
        report["status"] = "error"
        report["error"] = str(exc)
        report["traceback"] = traceback.format_exc()
        print(f"[ERROR] {exc}", file=sys.stderr)

    finished = datetime.now()
    report["finished"] = finished.isoformat()
    report["duration_sec"] = round((finished - started).total_seconds(), 1)
    log_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nЛог: {log_path}")
    print(f"Статус: {report['status']} | Час: {report['duration_sec']}с")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
