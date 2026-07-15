# -*- coding: utf-8 -*-
"""
Додає фільтр «Бренд» (param_id=5382) до всіх категорій, де він ще не активний.
Динамічно тягне (handler,mpa) з edit-сторінки кожної категорії (не хардкодить).

  python src/add_brand_filter_all.py --dry-run
  python src/add_brand_filter_all.py
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

from apply_horoshop_menu_fixes import auth, get_base_url, load_env  # noqa: E402
from fill_category_seo import walk_categories  # noqa: E402

BRAND_PID = "5382"
THROTTLE = 0.9
SKIP_IDS = {"1313", "1324", "1323"}  # архів, ветеранський спорт, сертифікати — ручні


def has_brand(html: str) -> bool:
    names = re.findall(r'class=.checked. id=.mpItem_\d+.>.*?<div>\s*([^<]+?)\s*</div>', html, re.S)
    return any("Бренд" in n for n in names)


def get_hid_mpa(html: str, cid: str) -> tuple[str, str] | None:
    m = re.search(r"addMPItem\((\d+),(\d+)," + cid + r",\d+,this\)", html)
    return (m.group(1), m.group(2)) if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    env = load_env()
    base = get_base_url(env)
    s = requests.Session()
    s.headers["User-Agent"] = "fish-sync-brand-filter/1.0"
    auth(s, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    tree = walk_categories(s, base)
    tree = [c for c in tree if c["id"] not in SKIP_IDS]
    print(f"Категорій: {len(tree)}")

    ok, skipped_has, skipped_nohid, failed = 0, 0, 0, []
    for i, c in enumerate(tree, 1):
        cid, parent = c["id"], c["parent"]
        try:
            r = s.get(f"{base}/adminLegacy/edit.php?id={cid}&parent={parent}&handler=4"
                      f"&checkcode=yamete_kudasai&showPages", timeout=60, verify=False)
            h = r.text
            if has_brand(h):
                skipped_has += 1
                continue
            hm = get_hid_mpa(h, cid)
            if not hm:
                skipped_nohid += 1
                continue
            hid, mpa = hm
            if args.dry_run:
                print(f"  [dry-run] {cid} «{c['title']}» → додав би Бренд (hid={hid} mpa={mpa})")
                ok += 1
                continue
            rr = s.get(f"{base}/adminLegacy/params/ajax_router.php",
                       params={"load": "addRecord", "handler": hid, "param": mpa,
                               "parent": cid, "binded_param": BRAND_PID,
                               "param_full_name": "multiparam_advanced",
                               "checkcode": "yamete_kudasai"},
                       headers={"X-Requested-With": "XMLHttpRequest",
                                "Referer": f"{base}/adminLegacy/edit.php?id={cid}&handler=4"},
                       timeout=60, verify=False)
            if "added" in rr.text or rr.status_code == 200:
                ok += 1
            else:
                failed.append({"id": cid, "title": c["title"], "resp": rr.text[:100]})
        except Exception as exc:
            failed.append({"id": cid, "title": c["title"], "err": str(exc)[:100]})
        if i % 20 == 0:
            print(f"  [{i}/{len(tree)}] додано={ok} вже_було={skipped_has} без_форми={skipped_nohid} помилок={len(failed)}")
        time.sleep(THROTTLE)

    print(f"\nГотово: додано={ok}, вже_мали={skipped_has}, без_форми={skipped_nohid}, помилок={len(failed)}")
    if failed:
        print(json.dumps(failed[:10], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
