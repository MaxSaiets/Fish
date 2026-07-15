# -*- coding: utf-8 -*-
"""
Повний аудит характеристик каталогу: для кожного товару за ОДИН GET
читає бренд, назву (title) і ВСІ характеристики (names[i18n][3][*]).
Мета: знайти залишки старого AI-опису, зафіксовані в дискретних полях
(не тільки Країна-виробник) - будь-яке поле, яке підозріло однакове
по ВСЬОМУ каталогу/сім'ї незалежно від бренду/моделі.

Резюмований (progress-файл пишеться кожні 50 товарів), throttle 1.4с.

  python src/full_catalog_char_audit.py
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

THROTTLE = 1.4
PROGRESS_FILE = ROOT / "data" / "full_char_audit_progress.json"

BRAND_SELECT_RE = re.compile(r"name=\"parent_common\[brand\]\">(.*?)</select>", re.S)
SELECTED_OPTION_RE = re.compile(r"<option value='(\d+)'\s*selected>([^<]*)</option>")
TITLE_RE = re.compile(r"name='parent_common\[i18n\]\[3\]\[title\]' value='([^']*)'")
PARAM_RE = re.compile(r"name='names\[i18n\]\[3\]\[(\w+)\]' value='([^']*)'")


def extract(html: str) -> dict:
    brand = ""
    m = BRAND_SELECT_RE.search(html)
    if m:
        m2 = SELECTED_OPTION_RE.search(m.group(1))
        if m2:
            brand = m2.group(2).strip()
    mt = TITLE_RE.search(html)
    title = mt.group(1).strip() if mt else ""
    params = {a: v.strip() for a, v in PARAM_RE.findall(html) if v.strip()}
    return {"brand": brand, "title": title, "params": params}


def main() -> int:
    env = load_env()
    base = get_base_url(env)
    s = requests.Session()
    s.headers["User-Agent"] = "fish-sync-full-char-audit/1.0"
    auth(s, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    articles = json.load(open(ROOT / "data" / "article_id_full.json", encoding="utf-8"))
    items = sorted(articles.items(), key=lambda kv: int(kv[1]))

    done: dict[str, dict] = {}
    if PROGRESS_FILE.exists():
        done = json.load(open(PROGRESS_FILE, encoding="utf-8"))
        print(f"Resume: {len(done)} вже готово", flush=True)

    total = len(items)
    checked_now = 0
    for art, pid in items:
        if art in done:
            continue
        try:
            r = s.get(
                f"{base}/adminLegacy/edit.php",
                params={"id": pid, "handler": "381", "checkcode": "yamete_kudasai"},
                timeout=30, verify=False,
            )
            rec = extract(r.text)
        except Exception as exc:
            rec = {"brand": "", "title": "", "params": {}, "err": str(exc)}
        rec["id"] = pid
        done[art] = rec
        checked_now += 1
        if checked_now % 50 == 0:
            json.dump(done, open(PROGRESS_FILE, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"[{len(done)}/{total}] нових={checked_now}", flush=True)
        time.sleep(THROTTLE)

    json.dump(done, open(PROGRESS_FILE, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\nГОТОВО: перевірено={len(done)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
