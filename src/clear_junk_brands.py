# -*- coding: utf-8 -*-
"""
Очищення поля "Бренд" (parent_common[brand], нативний select) для товарів,
де воно містить явно НЕ бренд (структурне слово/деталь оснастки/код),
а не назву виробника — знайдено при аналізі фільтра бренду на вітрині.

Консервативний список: тільки те, що не бренд І не правдоподібний
атрибут-фільтр (смак/колір лишається чіпати окремо, щоб не зламати
єдиний доступний фільтр для приманок).

  python src/clear_junk_brands.py --sample
  python src/clear_junk_brands.py
"""
from __future__ import annotations

import argparse
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

JUNK_BRANDS = {
    "сумка", "чорний", "обол.", "катушка", "вудлище", "сінінг", "вудилища",
    "струна", "на", "торба", "торба х2", "гач.", "плавунець з оком", "вуочка",
    "кг", "спіннінг", "спінінгnew", "вуlочка", "маховое", "red", "фідерні",
    "спиннинг", "в", "упаковці", "відв.", "повід.обол.", "наша снасть",
    "банан з вушком", "крапля з вушком обмазка з камінчиком", "кукулка з вушком",
    "кулька-око", "мідія з вушком", "німфаз вушком", "часничинка з отвором",
    "без полиці", "з полиці", "вдочка", "6.3", "коліно", "фідерн", "фідерне",
    "4821000003732", "хакі", "корич.", "стандарт", "без добавок",
}
PROGRESS_FILE = ROOT / "data" / "clear_junk_brands_progress.json"
THROTTLE = 1.3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()

    src = json.load(open(ROOT / "data" / "country_fix_progress.json", encoding="utf-8"))
    targets = [(art, v["id"]) for art, v in src.items()
               if v.get("brand", "").strip().lower() in JUNK_BRANDS]
    print(f"товарів зі сміттєвим брендом: {len(targets)}", flush=True)
    if args.sample:
        targets = targets[:5]
        print("sample:", targets, flush=True)

    done: dict[str, str] = {}
    if PROGRESS_FILE.exists():
        done = json.load(open(PROGRESS_FILE, encoding="utf-8"))
        print(f"Resume: {len(done)}", flush=True)

    env = load_env()
    base = get_base_url(env)
    s = requests.Session()
    s.headers["User-Agent"] = "fish-sync-clear-junk-brand/1.0"
    auth(s, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    ok = fail = 0
    for art, pid in targets:
        if art in done:
            continue
        try:
            url = f"{base}/adminLegacy/edit.php?id={pid}&parent=97&action=edit&handler=381&checkcode=yamete_kudasai"
            r = s.get(url, timeout=30, verify=False)
            p = LegacyFormParser()
            p.feed(r.text)
            f = dict(p.fields)
            payload = {k: v for k, v in f.items() if str(v) != ""}
            payload.update({
                "checkcode": "yamete_kudasai", "id": pid, "handler": "381",
                "handlertable": "h_product_characteristics", "back": "index.php",
            })
            payload["parent_common[brand]"] = "0"
            resp = post_form(s, f"{base}/adminLegacy/save.php", payload, url)
            if "HTTP_ERROR" in resp.text[:400]:
                raise RuntimeError(resp.text[:150])
            done[art] = "ok"
            ok += 1
        except Exception as exc:
            done[art] = f"ERROR:{str(exc)[:100]}"
            fail += 1
        if len(done) % 25 == 0:
            json.dump(done, open(PROGRESS_FILE, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"[{len(done)}/{len(targets)}] ok={ok} fail={fail}", flush=True)
        time.sleep(THROTTLE)

    json.dump(done, open(PROGRESS_FILE, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"ГОТОВО: ok={ok} fail={fail}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
