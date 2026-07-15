"""
Виправлення товарів, неадресованих через pricelist (артикули з провідними нулями/крапками):
оновлює title / mod_title / description / seo_title / seo_description НАПРЯМУ через
legacy-форму товару (edit.php?handler=381 → save.php) за internal id.

Вхід:
  data/unaddressable_articles_20260610.json  (629 артикулів)
  data/article_to_internal_id_20260610.json  (мапа з краулу datagrid)

Запуск:
  python src\\fix_products_by_form.py --check-victims   # перевірка 26 потенційних жертв колізій
  python src\\fix_products_by_form.py --limit 2         # тест
  python src\\fix_products_by_form.py                   # всі
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

from apply_horoshop_menu_fixes import LegacyFormParser, auth, get_base_url, load_env, post_form  # noqa: E402
from sync_content_playwright import build_product_seo  # noqa: E402


def fetch_product_form(session, base_url, pid: str) -> dict[str, str]:
    url = (f"{base_url}/adminLegacy/edit.php?id={urllib.parse.quote(pid)}"
           f"&parent=97&action=edit&handler=381&checkcode=yamete_kudasai")
    r = session.get(url, timeout=60, verify=False)
    r.raise_for_status()
    p = LegacyFormParser()
    p.feed(r.text)
    return dict(p.fields)


def save_product(session, base_url, pid: str, payload: dict) -> None:
    payload.update({
        "checkcode": "yamete_kudasai",
        "id": pid,
        "handler": "381",
        "back": "index.php",
    })
    post_form(session, f"{base_url}/adminLegacy/save.php", payload,
              f"{base_url}/adminLegacy/edit.php?id={pid}&handler=381")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--check-victims", action="store_true")
    args = ap.parse_args()

    una = json.load(open(ROOT / "data" / "unaddressable_articles_20260610.json", encoding="utf-8"))["unaddressable"]
    art2id = json.load(open(ROOT / "data" / "article_to_internal_id_20260610.json", encoding="utf-8"))

    from horoshop_catalog import build_canonical_products
    products = {str(p["article"]).strip(): p for p in build_canonical_products()}

    env = load_env()
    base = get_base_url(env)
    s = requests.Session()
    s.headers["User-Agent"] = "fish-sync-form-fix/1.0"
    auth(s, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    if args.check_victims:
        collisions = json.load(open(ROOT / "data" / "article_collisions_20260610.json", encoding="utf-8"))
        bad = 0
        for weird, victim in collisions:
            pid = art2id.get(victim)
            if not pid:
                print(f"  {victim}: нема в мапі")
                continue
            form = fetch_product_form(s, base, pid)
            live_title = form.get("parent_common[i18n][3][title]", "")
            want = products.get(victim, {}).get("title", "")
            wrong = products.get(weird, {}).get("title", "")
            status = "OK" if live_title == want else ("ПІДМІНЕНО!" if live_title == wrong else f"інше: {live_title[:50]}")
            if status != "OK":
                bad += 1
            print(f"  {victim} (id {pid}): {status}")
        print(f"victims перевірено: {len(collisions)}, проблемних: {bad}")
        return 0

    todo = [(a, art2id[a]) for a in una if a in art2id]
    print(f"unaddressable: {len(una)}, з internal id: {len(todo)}")
    if args.limit:
        todo = todo[: args.limit]

    report = {"started": datetime.now().isoformat(), "ok": 0, "skipped": [], "failed": []}
    for i, (art, pid) in enumerate(todo, 1):
        cp = products.get(art)
        if not cp:
            report["skipped"].append({"article": art, "reason": "no canonical"})
            continue
        try:
            form = fetch_product_form(s, base, pid)
            # sanity: форма належить саме цьому артикулу
            form_art = form.get("modifications[0][article]", "").strip()
            if form_art != art:
                report["skipped"].append({"article": art, "reason": f"form article mismatch: {form_art}"})
                continue
            title = str(cp["title"]).strip()
            seo_t, seo_d = build_product_seo(title, cp.get("price"))
            form["parent_common[i18n][3][title]"] = title
            form["modifications[0][i18n][3][mod_title]"] = title
            form["parent_common[i18n][3][description]"] = cp.get("description") or ""
            form["parent_common[i18n][3][seo_title]"] = seo_t
            form["parent_common[i18n][3][seo_description]"] = seo_d
            save_product(s, base, pid, form)
            report["ok"] += 1
            if i % 25 == 0 or i == len(todo):
                print(f"[{i}/{len(todo)}] ok={report['ok']} skip={len(report['skipped'])} fail={len(report['failed'])}")
        except Exception as exc:
            report["failed"].append({"article": art, "id": pid, "error": str(exc)[:160]})

    report["finished"] = datetime.now().isoformat()
    out = ROOT / "data" / f"form_fix_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Звіт: {out} | ok={report['ok']} skipped={len(report['skipped'])} failed={len(report['failed'])}")
    return 0


if __name__ == "__main__":
    sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
