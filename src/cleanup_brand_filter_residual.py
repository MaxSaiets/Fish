# -*- coding: utf-8 -*-
"""
Дочистка фільтра "Бренд": залишки, невидимі у формах товарів.

Виявлено 2026-07-16: фільтр індексує бренд з таблиці, яку пише ТІЛЬКИ
pricelist-імпорт; у частини товарів форма показує "[оберіть]" (порожньо),
а фільтр досі відносить їх до старого значення (Carp, Afeima, FISHING...).
Тому джерело правди для дочистки — самі фільтри вітрини:
  1) обходимо всі категорії, збираємо значення фільтра Бренд (name+id);
  2) для сміттєвих/мапованих значень відкриваємо сторінку
     /category/filter/brand=ID/ і збираємо артикули з карток товарів;
  3) один pricelist-імпорт: артикул → нове значення ('' = очистити).

  python src/cleanup_brand_filter_residual.py --dry-run
  python src/cleanup_brand_filter_residual.py
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

from import_parent_brand import build_xls, run_import  # noqa: E402
from sync_content_playwright import load_env  # noqa: E402
from cleanup_brand_filter import CLEAR, MAP  # noqa: E402

ART_TD = "<td style=\"mso-number-format:'\\@';\">"
BASE = "https://vsedliarybalky.com.ua"
REPORT = ROOT / "data" / "brand_residual_cleanup_20260716.json"


def storefront_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"
    home = s.get(BASE + "/", timeout=30, verify=False)
    m = re.search(r'defaultHash\s*=\s*"([0-9a-f]+)"', home.text)
    if m:
        s.cookies.set("challenge_passed", m.group(1))
    return s


def category_slugs(s: requests.Session) -> list[str]:
    """Всі категорійні slug'и з sitemap."""
    slugs: set[str] = set()
    sm = s.get(BASE + "/sitemap.xml", timeout=30, verify=False).text
    for sub in re.findall(r"<loc>([^<]+)</loc>", sm):
        if "catalog-sitemap" in sub:
            continue  # то товарні
        if sub.rstrip("/").count("/") == 3 and sub.endswith("/"):
            slugs.add(sub.replace(BASE, ""))
    # надійніше: пройтись по головному меню
    home = s.get(BASE + "/", timeout=30, verify=False).text
    for href in re.findall(r'href="(/[a-z0-9\-]+/)"', home):
        slugs.add(href)
    bad = {"/blog/", "/checkout/", "/sertyfikaty/"}
    return sorted(x for x in slugs if x not in bad and len(x) > 3)


def brand_values(s: requests.Session, slug: str) -> list[tuple[str, str, int]]:
    """(brand_id, name, count) зі сторінки категорії."""
    r = s.get(BASE + slug, timeout=30, verify=False)
    if r.status_code != 200:
        return []
    out = []
    for m in re.finditer(
        r'data-fake-href="[^"]*?/filter/brand=(\d+)/"[^>]*>.*?filter-title[^>]*>([^<]+)<.*?filter-count">(\d+)<',
        r.text, re.S):
        out.append((m.group(1), html_mod.unescape(m.group(2)).strip(), int(m.group(3))))
    return out


_ARTICLE_CACHE: dict[str, str] = {}


def collect_product_urls(s: requests.Session, slug: str, brand_id: str) -> set[str]:
    urls: set[str] = set()
    for page in range(1, 8):
        url = BASE + (f"{slug}filter/brand={brand_id};page={page}/" if page > 1
                      else f"{slug}filter/brand={brand_id}/")
        r = s.get(url, timeout=30, verify=False)
        found = set(re.findall(r"catalogCard-title\">\s*<a href='(/[^']+/\d+/)'", r.text))
        new = found - urls
        if not new:
            break
        urls |= new
        time.sleep(0.2)
    return urls


def article_of(s: requests.Session, product_url: str) -> str | None:
    if product_url in _ARTICLE_CACHE:
        return _ARTICLE_CACHE[product_url]
    r = s.get(BASE + product_url, timeout=30, verify=False)
    m = re.search(r"Артикул</span>\s*([^<\s][^<]*?)\s*</", r.text)
    art = m.group(1).strip() if m else None
    if art:
        _ARTICLE_CACHE[product_url] = art
    return art


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    s = storefront_session()
    slugs = category_slugs(s)
    print(f"категорій для обходу: {len(slugs)}", flush=True)

    # 1) зібрати всі значення фільтрів
    targets: dict[str, dict] = {}   # brand_id -> {'name','slugs':[]}
    for i, slug in enumerate(slugs, 1):
        for bid, name, cnt in brand_values(s, slug):
            new_val = MAP.get(name)
            if name in CLEAR:
                new_val = ""
            if new_val is None:
                continue
            t = targets.setdefault(bid, {"name": name, "new": new_val, "slugs": []})
            t["slugs"].append(slug)
        if i % 25 == 0:
            print(f"  [{i}/{len(slugs)}] цілей: {len(targets)}", flush=True)
        time.sleep(0.25)

    print(f"сміттєвих/мапованих значень у фільтрах: {len(targets)}", flush=True)
    for bid, t in targets.items():
        print(f"  id={bid} {t['name']!r} -> {t['new']!r} ({len(t['slugs'])} катег.)", flush=True)

    # 2) товари → артикули
    rows: list[tuple[str, str]] = []
    for bid, t in targets.items():
        purls: set[str] = set()
        for slug in t["slugs"]:
            purls |= collect_product_urls(s, slug, bid)
            time.sleep(0.2)
        arts: set[str] = set()
        for pu in purls:
            a = article_of(s, pu)
            if a:
                arts.add(a)
            time.sleep(0.2)
        print(f"  {t['name']!r}: товарів={len(purls)} артикулів={len(arts)}", flush=True)
        rows += [(a, t["new"]) for a in sorted(arts)]

    # дедуп: останнє значення виграє (не критично)
    dedup: dict[str, str] = {}
    for a, v in rows:
        dedup[a] = v
    rows = sorted(dedup.items())
    print(f"усього правок: {len(rows)}", flush=True)
    REPORT.write_text(json.dumps({"targets": targets, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")

    if args.dry_run or not rows:
        return 0

    html_rows = [f"<tr>{ART_TD}{html_mod.escape(a)}</td><td>{html_mod.escape(v)}</td></tr>" for a, v in rows]
    xls = build_xls(html_rows, ["Артикул", "Бренд"])
    out = ROOT / "tmp" / "import_brand_residual.xls"
    out.write_bytes(xls)
    env = load_env()
    base = env.get("HOROSHOP_BASE_URL", BASE).rstrip("/")
    res = run_import(out, ["article", "brand"], base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])
    print("Результат:", res, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
