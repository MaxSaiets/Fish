# -*- coding: utf-8 -*-
"""
Комбінований аудит+фікс поля "Країна-виробник" (один прохід замість двох):
GET форми -> рішення -> одразу POST виправлення, якщо треба.

Політика (лише для kranaVirobnik, нічого іншого не чіпає):
  - бренд Є в перевіреній мапі BRAND_COUNTRY і поточне значення НЕ збігається
    -> виправити на мапне значення (висока впевненість);
  - бренд НЕВІДОМИЙ мапі і поточне значення = "Україна"
    -> ОЧИСТИТИ (підтверджено: залишок старого AI-опису, неправдива заява);
  - інакше -> не чіпати.

throttle 0.55с (~1.8 rps, у межах дозволеного тарифом "1-2 rps").
Резюмований: data/country_fix_progress.json.

  python src/fix_country_field.py
"""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

from apply_horoshop_menu_fixes import LegacyFormParser, auth, get_base_url, load_env, post_form  # noqa: E402
from param_enrichment import BRAND_COUNTRY  # noqa: E402

THROTTLE = 0.55
PROGRESS_FILE = ROOT / "data" / "country_fix_progress.json"
FIELD = "names[i18n][3][kranaVirobnik]"


def main() -> int:
    env = load_env()
    base = get_base_url(env)
    s = requests.Session()
    s.headers["User-Agent"] = "fish-sync-country-fix/1.0"
    auth(s, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    articles = json.load(open(ROOT / "data" / "article_id_full.json", encoding="utf-8"))
    brand_map = json.load(open(ROOT / "data" / "brand_id_to_name.json", encoding="utf-8"))

    done: dict[str, dict] = {}
    if PROGRESS_FILE.exists():
        done = json.load(open(PROGRESS_FILE, encoding="utf-8"))
        print(f"Resume: {len(done)} вже готово", flush=True)

    from horoshop_catalog import build_canonical_products
    qty_by_article = {str(p["article"]).strip(): int(p.get("quantity") or 0) for p in build_canonical_products()}

    def in_stock(art: str) -> bool:
        return qty_by_article.get(art, 0) > 0

    items = sorted(
        articles.items(),
        key=lambda kv: (0 if in_stock(kv[0]) else 1, int(kv[1])),
    )

    total = len(items)
    corrected = 0
    cleared = 0
    checked_now = 0
    failed = 0
    for art, pid in items:
        if art in done:
            continue
        try:
            url = (f"{base}/adminLegacy/edit.php?id={pid}&parent=97"
                   f"&action=edit&handler=381&checkcode=yamete_kudasai")
            r = s.get(url, timeout=30, verify=False)
            p = LegacyFormParser()
            p.feed(r.text)
            f = dict(p.fields)
            brand_id = f.get("parent_common[brand]", "")
            brand_name = brand_map.get(brand_id, "")
            current = f.get(FIELD, "").strip()
            mapped = BRAND_COUNTRY.get(brand_name.strip().lower(), "")

            action = "none"
            new_value = current
            if current and mapped and current != mapped:
                action, new_value = "correct", mapped
            elif current == "Україна" and not mapped:
                action, new_value = "clear", ""

            if action != "none":
                payload = {k: v for k, v in f.items() if str(v) != ""}
                payload.update({
                    "checkcode": "yamete_kudasai", "id": pid, "handler": "381",
                    "handlertable": "h_product_characteristics", "back": "index.php",
                })
                payload[FIELD] = new_value
                resp = post_form(s, f"{base}/adminLegacy/save.php", payload, url)
                if "HTTP_ERROR" in resp.text[:400]:
                    raise RuntimeError(resp.text[:150])
                time.sleep(THROTTLE)
                if action == "correct":
                    corrected += 1
                else:
                    cleared += 1

            done[art] = {"id": pid, "brand": brand_name, "before": current, "action": action, "after": new_value}
        except Exception as exc:
            done[art] = {"id": pid, "action": "ERROR", "error": str(exc)[:150]}
            failed += 1
        checked_now += 1
        if checked_now % 50 == 0:
            json.dump(done, open(PROGRESS_FILE, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"[{len(done)}/{total}] виправлено={corrected} очищено={cleared} помилок={failed}", flush=True)
        time.sleep(THROTTLE)

    json.dump(done, open(PROGRESS_FILE, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\nГОТОВО: перевірено={len(done)}, виправлено={corrected}, очищено={cleared}, помилок={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
