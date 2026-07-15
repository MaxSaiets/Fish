# -*- coding: utf-8 -*-
"""
Масовий імпорт: перенесення розділу (parent) та/або заповнення бренду
через штатний pricelist-імпорт (Playwright, ~6-8 запитів на прогін).

  python src/import_parent_brand.py --mode parent --sample     # тест 1 товару
  python src/import_parent_brand.py --mode parent              # всі 916
  python src/import_parent_brand.py --mode brand               # всі 958
"""
from __future__ import annotations

import argparse
import html as html_mod
import io
import json
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

from sync_content_playwright import _login_horoshop, load_env  # noqa: E402

SCRATCHES = [
    Path(r"C:\Users\sayet\AppData\Local\Temp\claude\D--FISH\f8800df7-a742-4951-9aa4-b8b05cc12804\scratchpad"),
    Path(r"C:\Users\sayet\AppData\Local\Temp\claude\D--FISH\1b16c474-a7bb-4165-a51f-f6ce2f363819\scratchpad"),
]
SILICONE_PARENT = "Приманки / Силіконові приманки"
ART_TD = "<td style=\"mso-number-format:'\\@';\">"


def scratch_file(name: str) -> Path:
    for s in SCRATCHES:
        if (s / name).exists():
            return s / name
    raise FileNotFoundError(name)


def build_xls(rows_html: list[str], headers: list[str]) -> bytes:
    head = "".join(f"<th>{h}</th>" for h in headers)
    html = (
        "<html xmlns:x=\"urn:schemas-microsoft-com:office:excel\">"
        "<head><meta charset=\"utf-8\"></head><body><table border=1>"
        f"<tr>{head}</tr>" + "".join(rows_html) + "</table></body></html>"
    )
    return html.encode("utf-8")


def run_import(xls_path: Path, field_values: list[str], base: str, login: str, pwd: str,
               import_type: str = "item", handler: str | None = None) -> str:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126")
        page = ctx.new_page()
        page.goto(f"{base}/", wait_until="domcontentloaded", timeout=20000)
        _login_horoshop(page, base, login, pwd)
        page.wait_for_timeout(500)
        page.goto(f"{base}/adminLegacy/import/pricelist.php", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1000)

        sel = page.query_selector("select[name='import_type'], select[name='type']")
        if sel:
            opts = sel.evaluate("el => [...el.options].map(o => o.value)")
            if import_type in opts:
                sel.select_option(import_type)
            else:
                for o in ("item", "products", "product"):
                    if o in opts:
                        sel.select_option(o)
                        break
        if handler:
            page.wait_for_timeout(300)
            hsel = page.query_selector("select[name='handler']")
            if hsel:
                hsel.select_option(handler)
        page.set_input_files("input[type='file']", str(xls_path))
        page.wait_for_timeout(400)
        btn = page.query_selector("input[type='submit'], button[type='submit']")
        btn.click()
        page.wait_for_load_state("networkidle", timeout=120000)
        page.wait_for_timeout(1500)

        selects = page.query_selector_all("select[name^='col_'], select[name^='column_'], select[name^='field_']")
        if not selects:
            selects = page.query_selector_all("select")
        print(f"  мапінг: {len(selects)} select-полів, ставлю {field_values}")
        for s_el, val in zip(selects, field_values):
            avail = s_el.evaluate("el => [...el.options].map(o => o.value)")
            if val in avail:
                s_el.select_option(val)
            else:
                match = next((a for a in avail if val in a), None)
                if match:
                    s_el.select_option(match)
                else:
                    print(f"  [!] немає option '{val}' серед {avail[:12]}")
        page.wait_for_timeout(400)
        btn2 = page.query_selector("input[type='submit'], button[type='submit']")
        btn2.click()
        page.wait_for_load_state("networkidle", timeout=300000)
        page.wait_for_timeout(2500)
        body = page.inner_text("body")
        browser.close()
        m = re.findall(r"(Обновлено|Оновлено|Добавлено|Створено|Updated)[^\d]{0,10}(\d+)", body)
        tail = body[-600:].replace("\n", " ")
        return f"{m if m else tail[:300]}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["parent", "brand"], required=True)
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()

    if args.mode == "parent":
        arts = json.load(open(scratch_file("silicone_move_plan.json"), encoding="utf-8"))
        if args.sample:
            arts = arts[:1]
        rows = [f"<tr>{ART_TD}{html_mod.escape(a)}</td>"
                f"<td>{html_mod.escape(SILICONE_PARENT)}</td></tr>" for a in arts]
        xls = build_xls(rows, ["Артикул", "Розділ"])
        fields = ["article", "parent"]
        print(f"Імпорт parent: {len(arts)} товарів → «{SILICONE_PARENT}»")
        if args.sample:
            print("  sample-артикул:", arts[0])
    else:
        plan = json.load(open(scratch_file("brand_fill_plan.json"), encoding="utf-8"))
        items = sorted(plan.items())
        if args.sample:
            items = items[:1]
        rows = [f"<tr>{ART_TD}{html_mod.escape(a)}</td>"
                f"<td>{html_mod.escape(b)}</td></tr>" for a, b in items]
        xls = build_xls(rows, ["Артикул", "Бренд"])
        fields = ["article", "brand"]
        print(f"Імпорт brand: {len(items)} товарів")
        if args.sample:
            print("  sample:", items[0])

    out = ROOT / "tmp" / f"import_{args.mode}{'_sample' if args.sample else ''}.xls"
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(xls)

    env = load_env()
    base = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    res = run_import(out, fields, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])
    print("Результат:", res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
