# -*- coding: utf-8 -*-
"""
Аудит поля "Країна-виробник" по всьому каталогу: для кожного товару читає
живу форму (бренд + kranaVirobnik), звіряє з перевіреною мапою BRAND_COUNTRY.
Знаходить залишки старого AI-опису ("Країна-виробник: Україна" хардкод),
які не відповідають реальному бренду.

Резюмований (progress-файл), throttle 1.5с (1 потік, ~0.66 rps).

  python src/audit_country_field.py
"""
from __future__ import annotations

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
from param_enrichment import BRAND_COUNTRY  # noqa: E402

THROTTLE = 1.5
PROGRESS_FILE = ROOT / "data" / "country_field_audit_progress.json"
RESULT_FILE = ROOT / "data" / "country_field_audit_full.json"

BRAND_SELECT_RE = re.compile(
    r"name=\"parent_common\[brand\]\">(.*?)</select>", re.S
)
SELECTED_OPTION_RE = re.compile(r"<option value='(\d+)'\s*selected>([^<]*)</option>")
COUNTRY_RE = re.compile(r"name='names\[i18n\]\[3\]\[kranaVirobnik\]' value='([^']*)'")


def extract(html: str) -> tuple[str, str]:
    brand = ""
    m = BRAND_SELECT_RE.search(html)
    if m:
        m2 = SELECTED_OPTION_RE.search(m.group(1))
        if m2:
            brand = m2.group(2).strip()
    country = ""
    m3 = COUNTRY_RE.search(html)
    if m3:
        country = m3.group(1).strip()
    return brand, country


def main() -> int:
    env = load_env()
    base = get_base_url(env)
    s = requests.Session()
    s.headers["User-Agent"] = "fish-sync-country-audit/1.0"
    auth(s, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    articles = json.load(open(ROOT / "data" / "article_id_full.json", encoding="utf-8"))
    items = sorted(articles.items(), key=lambda kv: int(kv[1]))

    done: dict[str, dict] = {}
    if PROGRESS_FILE.exists():
        done = json.load(open(PROGRESS_FILE, encoding="utf-8"))
        print(f"Resume: {len(done)} вже готово", flush=True)

    total = len(items)
    suspect = 0
    checked_now = 0
    for i, (art, pid) in enumerate(items, 1):
        if art in done:
            continue
        try:
            r = s.get(
                f"{base}/adminLegacy/edit.php",
                params={"id": pid, "handler": "381", "checkcode": "yamete_kudasai"},
                timeout=30, verify=False,
            )
            brand, country = extract(r.text)
        except Exception as exc:
            brand, country = "", f"ERR:{exc}"
        mapped = BRAND_COUNTRY.get(brand.strip().lower(), "")
        status = "ok"
        if country == "Україна" and mapped and mapped != "Україна":
            status = "wrong_mismatch"  # бренд впевнено НЕ українського походження
        elif country == "Україна" and not mapped:
            status = "unverified_ua"  # бренд не в перевіреній мапі - підозріле
        elif country and mapped and country != mapped:
            status = "other_mismatch"
        done[art] = {"id": pid, "brand": brand, "country": country, "mapped": mapped, "status": status}
        checked_now += 1
        if status != "ok":
            suspect += 1
        if checked_now % 50 == 0:
            json.dump(done, open(PROGRESS_FILE, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"[{len(done)}/{total}] нових={checked_now} підозрілих_всього={suspect}", flush=True)
        time.sleep(THROTTLE)

    json.dump(done, open(PROGRESS_FILE, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(done, open(RESULT_FILE, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\nГОТОВО: перевірено={len(done)}, підозрілих={suspect}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
