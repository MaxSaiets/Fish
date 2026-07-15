"""
Імпорт КОНТЕНТУ (назва + опис) у Horoshop через adminLegacy/import/pricelist.php (Playwright).

Той самий перевірений механізм, що й sync_stock_playwright.py (працює погодинно),
але замість price/presence веземо title/description з канонічного каталогу
(horoshop_catalog.build_canonical_products → нові еталонні описи без AI-кліше).

Колонки і значення мапінгу (підтверджені в data/template381_matched_only_mapping_plan_20260607.csv):
  col_0 = Артикул            -> article
  col_1 = Назва(ua)          -> title-_-3
  col_2 = Опис товару(ua)    -> description-_-3

Режими кодування опису в HTML-XLS (--desc-mode):
  raw    — HTML-опис як вкладена розмітка у <td> (парсер бере innerText — теги ГУБЛЯТЬСЯ)
  escape — html.escape() — ПРАВИЛЬНИЙ режим (default): Horoshop розекранує і зберігає
           справжній HTML, на сторінці рендеряться <p> та <ul> (перевірено 2026-06-10)
  strip  — чистий текст без тегів (аварійний фолбек)

Запуск:
  python src\\sync_content_playwright.py --sample          # 5 безпечних артикулів
  python src\\sync_content_playwright.py --articles 3762,3759
  python src\\sync_content_playwright.py --dry-run
  python src\\sync_content_playwright.py                   # повний каталог
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
LOG_DIR = ROOT / "logs"
TMP_DIR = ROOT / "tmp"
sys.path.insert(0, str(ROOT / "src"))

SAMPLE_ARTICLES = ["3762", "3759", "4452", "3760", "3761"]

# Значення option'ів у dropdown мапінгу pricelist.php
FIELD_VALUES = ["article", "title-_-3", "description-_-3"]
FIELD_VALUES_MOD = ["article", "title-_-3", "mod_title-_-3", "description-_-3"]
# Повний набір для СТВОРЕННЯ нових товарів (категорія + бренд + ціна + наявність)
FIELD_VALUES_CREATE = [
    "article", "title-_-3", "mod_title-_-3", "parent", "brand",
    "price", "currency", "presence", "description-_-3",
]
# SEO-поля товару (перезаписують глобальний SEO-шаблон на рівні товару)
FIELD_VALUES_SEO = ["article", "seo_title-_-3", "seo_description-_-3"]

SHOP_NAME = "Все для рибалки"


def build_product_seo(title: str, price) -> tuple[str, str]:
    seo_title = f"{title} — купити в Україні | {SHOP_NAME}"
    if len(seo_title) > 80:
        seo_title = f"{title} | купити — {SHOP_NAME}"
    try:
        price_part = f"{float(price):g} грн ✓ " if float(price) > 0 else ""
    except (TypeError, ValueError):
        price_part = ""
    seo_description = (
        f"{title} в наявності ✓ {price_part}Доставка Новою поштою по Україні ✓ "
        f"Обмін і повернення 14 днів. Замовляйте в інтернет-магазині «{SHOP_NAME}»."
    )[:250]
    return seo_title, seo_description


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


def clean_cell_text(value: str) -> str:
    return " ".join(str(value or "").split())


def generate_content_xls(items: list[dict], desc_mode: str, mode: str = "basic") -> bytes:
    from horoshop_catalog import strip_html

    rows = []
    # mso-number-format:'\@' — змушує парсер бачити артикул ТЕКСТОМ:
    # без цього артикули виду "00.10" / "0000006" парсяться як числа і випадають
    art_td = "<td style=\"mso-number-format:'\\@';\">"
    for it in items:
        article = html_mod.escape(clean_cell_text(it["article"]))
        title = html_mod.escape(clean_cell_text(it["title"]))
        desc_html = it.get("description") or ""
        if desc_mode == "raw":
            desc_cell = clean_cell_text(desc_html)  # вкладена розмітка лишається тегами
        elif desc_mode == "escape":
            desc_cell = html_mod.escape(clean_cell_text(desc_html))
        else:  # strip
            desc_cell = html_mod.escape(clean_cell_text(strip_html(desc_html)))
        if mode == "seo":
            st, sd = build_product_seo(clean_cell_text(it["title"]), it.get("price"))
            rows.append(f"<tr>{art_td}{article}</td><td>{html_mod.escape(st)}</td><td>{html_mod.escape(sd)}</td></tr>")
            continue
        if mode == "create":
            parent = html_mod.escape(clean_cell_text(it.get("parent") or ""))
            brand = html_mod.escape(clean_cell_text(it.get("brand") or ""))
            price = html_mod.escape(clean_cell_text(str(it.get("price") or "")))
            currency = html_mod.escape(clean_cell_text(it.get("currency") or "UAH"))
            presence = html_mod.escape(clean_cell_text(it.get("presence") or ""))
            rows.append(
                f"<tr>{art_td}{article}</td><td>{title}</td><td>{title}</td><td>{parent}</td>"
                f"<td>{brand}</td><td>{price}</td><td>{currency}</td><td>{presence}</td>"
                f"<td>{desc_cell}</td></tr>"
            )
        elif mode == "mod":
            rows.append(f"<tr>{art_td}{article}</td><td>{title}</td><td>{title}</td><td>{desc_cell}</td></tr>")
        else:
            rows.append(f"<tr>{art_td}{article}</td><td>{title}</td><td>{desc_cell}</td></tr>")

    if mode == "seo":
        header = "<tr><th>article</th><th>seo_title</th><th>seo_description</th></tr>"
    elif mode == "create":
        header = ("<tr><th>article</th><th>title</th><th>mod_title</th><th>parent</th><th>brand</th>"
                  "<th>price</th><th>currency</th><th>presence</th><th>description</th></tr>")
    elif mode == "mod":
        header = "<tr><th>article</th><th>title</th><th>mod_title</th><th>description</th></tr>"
    else:
        header = "<tr><th>article</th><th>title</th><th>description</th></tr>"
    html = (
        '<html><head><meta charset="UTF-8"></head><body>'
        "<table>" + header
        + "\n".join(rows)
        + "</table></body></html>"
    )
    return html.encode("utf-8")


def _login_horoshop(page, base_url: str, login: str, password: str) -> None:
    result = page.evaluate(
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
    items: list[dict],
    base_url: str,
    login: str,
    password: str,
    desc_mode: str,
    headful: bool = False,
    dry_run: bool = False,
    mode: str = "basic",
) -> dict:
    from playwright.sync_api import sync_playwright

    stats: dict = {"total": len(items), "status": "ok", "dry_run": dry_run, "desc_mode": desc_mode, "mode": mode}
    field_values = {"create": FIELD_VALUES_CREATE, "mod": FIELD_VALUES_MOD, "seo": FIELD_VALUES_SEO}.get(mode, FIELD_VALUES)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    xls_path = TMP_DIR / "content_upload.xls"
    xls_path.write_bytes(generate_content_xls(items, desc_mode, mode))
    print(f"XLS згенеровано: {xls_path} ({len(items)} товарів, desc_mode={desc_mode}, mode={mode})")

    if dry_run:
        print(f"[dry-run] upload пропущено")
        return stats

    import_url = f"{base_url}/adminLegacy/import/pricelist.php"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headful)
        context = browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126",
        )
        page = context.new_page()

        print("Логін у Horoshop...")
        page.goto(f"{base_url}/", wait_until="domcontentloaded", timeout=15000)
        _login_horoshop(page, base_url, login, password)
        page.wait_for_timeout(500)

        print(f"Перехід на: {import_url}")
        page.goto(import_url, wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(1000)

        import_type_sel = page.query_selector("select[name='import_type'], select[name='type']")
        if import_type_sel:
            options = import_type_sel.evaluate("el => [...el.options].map(o => o.value)")
            for opt in ("item", "products", "product"):
                if opt in options:
                    import_type_sel.select_option(opt)
                    print(f"  import_type = {opt}")
                    break
            page.wait_for_timeout(300)

        file_input = page.query_selector("input[type='file']")
        if not file_input:
            ss_path = TMP_DIR / "debug_content_step1.png"
            page.screenshot(path=str(ss_path))
            raise RuntimeError(f"Не знайдено input[type=file]. URL: {page.url}. Screenshot: {ss_path}")

        print(f"  Вибираємо файл: {xls_path.name}")
        file_input.set_input_files(str(xls_path))
        page.wait_for_timeout(500)

        submit1 = page.query_selector("input[type='submit'], button[type='submit']")
        if submit1:
            submit1.click()
        else:
            page.evaluate("document.querySelector('form').submit()")

        page.wait_for_load_state("networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        print(f"  Після step1 URL: {page.url}")

        col_selects = page.query_selector_all("select[name^='col_'], select[name^='column_'], select[name^='field_']")
        if not col_selects:
            col_selects = page.query_selector_all("select")
        print(f"  Знайдено {len(col_selects)} select-полів для мапінгу")

        mapped = []
        for i, (sel, field_value) in enumerate(zip(col_selects[: len(field_values)], field_values)):
            try:
                available = sel.evaluate("el => [...el.options].map(o => o.value)")
                if field_value in available:
                    sel.select_option(field_value)
                    mapped.append(field_value)
                    print(f"  col_{i} -> {field_value}")
                else:
                    match = next((v for v in available if field_value.split("-_-")[0] in v.lower()), None)
                    if match:
                        sel.select_option(match)
                        mapped.append(match)
                        print(f"  col_{i} -> {match} (замість {field_value})")
                    else:
                        print(f"  [WARN] col_{i}: '{field_value}' не знайдено. Доступні: {available[:10]}")
            except Exception as e:
                print(f"  [WARN] col_{i} мапінг: {e}")
        stats["mapped"] = mapped

        if len(mapped) < len(field_values):
            ss_path = TMP_DIR / "debug_content_mapping.png"
            page.screenshot(path=str(ss_path))
            stats["status"] = "mapping_failed"
            stats["screenshot"] = str(ss_path)
            browser.close()
            return stats

        page.evaluate("""
            const form = document.querySelector('form[method=post]') || document.querySelector('form');
            if (form) { form.submit(); } else { console.warn('no form found'); }
        """)

        page.wait_for_load_state("networkidle", timeout=180000)
        page.wait_for_timeout(2000)

        final_url = page.url
        result_text = page.locator("body").inner_text(timeout=180000)
        print(f"  Фінальна URL: {final_url}")
        print(f"  Результат (перші 400): {result_text[:400]}")

        stats["result_url"] = final_url
        stats["result_preview"] = result_text[:300]

        import re as _re
        html_source = page.content()
        # повний результат: постатейні статуси (Обновлен/Добавлен/...)
        result_html_path = TMP_DIR / "last_content_result.html"
        result_html_path.write_text(html_source, encoding="utf-8")
        statuses = _re.findall(
            r"<td[^>]*>([^<\t]{1,60}?)</td>\s*<td[^>]*>[^<]*</td>\s*<td[^>]*>(Обновлен|Добавлен|Не найден|Ошибка)[^<]*</td>",
            html_source,
        )
        if statuses:
            from collections import Counter as _Counter
            stats["per_status"] = dict(_Counter(st for _, st in statuses))
            arts_path = LOG_DIR / f"content_result_articles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            arts_path.write_text(
                json.dumps([{"article": a.strip(), "status": st} for a, st in statuses],
                           ensure_ascii=False), encoding="utf-8")
            stats["articles_log"] = str(arts_path)
            print(f"  Постатейні статуси: {stats['per_status']}")
        updated_match = (
            _re.search(r"[Оо]бновлено[:\s]+(\d+)", result_text)
            or _re.search(r"[Оо]новлено[:\s]+(\d+)", result_text)
            or _re.search(r"[Оо]бновлено[:\s]+(\d+)", html_source)
            or _re.search(r"[Оо]новлено[:\s]+(\d+)", html_source)
        )
        errors_match = (
            _re.search(r"[Пп]омилок[:\s]+(\d+)", result_text)
            or _re.search(r"[Оо]шибок[:\s]+(\d+)", html_source)
            or _re.search(r"[Пп]омилок[:\s]+(\d+)", html_source)
        )
        stats["updated"] = int(updated_match.group(1)) if updated_match else -1
        stats["errors"] = int(errors_match.group(1)) if errors_match else -1

        ss_path = TMP_DIR / "last_content_sync_result.png"
        page.screenshot(path=str(ss_path))
        stats["screenshot"] = str(ss_path)

        if stats["updated"] > 0:
            stats["status"] = "ok" if stats["errors"] <= 0 else "warning"
        elif final_url.endswith("pricelist.php"):
            stats["status"] = "ok"
        else:
            stats["status"] = "unknown"

        browser.close()

    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description="Імпорт назв+описів у Horoshop через Playwright")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--sample", action="store_true", help="Тільки 5 безпечних артикулів")
    ap.add_argument("--articles", type=str, default=None, help="Список артикулів через кому")
    ap.add_argument("--articles-file", type=str, default=None,
                    help="Файл зі списком артикулів через кому (обхід ліміту командного рядка)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--desc-mode", choices=["raw", "escape", "strip"], default="escape")
    ap.add_argument("--with-mod-title", action="store_true",
                    help="(застаріле) те саме, що --mode mod")
    ap.add_argument("--mode", choices=["basic", "mod", "create", "seo"], default=None,
                    help="basic: назва+опис; mod: + назва модифікації (ОНОВЛЕННЯ існуючих); "
                         "create: + Розділ/Бренд/Ціна/Валюта/Наявність (СТВОРЕННЯ нових товарів); "
                         "seo: HTML title + META description на рівні товару")
    args = ap.parse_args()
    mode = args.mode or ("mod" if args.with_mod_title else "basic")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"content_pw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    started = datetime.now()
    report: dict = {"started": started.isoformat(), "args": vars(args)}

    try:
        from horoshop_catalog import build_canonical_products

        products = build_canonical_products()
        items = [
            {
                "article": str(p.get("article") or "").strip(),
                "title": str(p.get("title") or "").strip(),
                "description": p.get("description") or "",
                "parent": p.get("parent") or "",
                "brand": p.get("brand") or "",
                "price": p.get("price") or "",
                "currency": p.get("currency") or "UAH",
                "presence": p.get("presence") or "",
            }
            for p in products
            if str(p.get("article") or "").strip() and str(p.get("title") or "").strip()
        ]

        if args.sample:
            wanted = set(SAMPLE_ARTICLES)
            items = [it for it in items if it["article"] in wanted]
        elif args.articles or args.articles_file:
            raw_list = args.articles or ""
            if args.articles_file:
                raw_list = Path(args.articles_file).read_text(encoding="utf-8")
            wanted = {a.strip() for a in raw_list.split(",") if a.strip()}
            items = [it for it in items if it["article"] in wanted]
        if args.limit:
            items = items[: args.limit]

        print(f"До імпорту: {len(items)} товарів")
        report["items"] = len(items)
        if not items:
            raise RuntimeError("Порожній список товарів")

        env = load_env()
        base = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
        login = env.get("HOROSHOP_LOGIN", "")
        password = env.get("HOROSHOP_PASS", "")

        stats = sync_via_playwright(
            items, base, login, password,
            desc_mode=args.desc_mode, headful=args.headful, dry_run=args.dry_run,
            mode=mode,
        )
        report["sync"] = stats
        report["status"] = stats.get("status", "unknown")

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
    return 0 if report["status"] in ("ok", "warning") else 1


if __name__ == "__main__":
    sys.exit(main())
