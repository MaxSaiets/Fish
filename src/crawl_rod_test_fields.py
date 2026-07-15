# -*- coding: utf-8 -*-
"""
Збирає з живих форм значення test/casting_test для вудилищ,
щоб точно знайти дублі (site-side). Резюмований, throttle 1.2с.
"""
from __future__ import annotations

import io
import json
import re
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

from apply_horoshop_menu_fixes import auth, get_base_url, load_env  # noqa: E402

OUT = ROOT / "data" / "rod_test_fields.json"
ROD_WORD = re.compile(r"^(Спінінг|Спиннинг|Спіннінг|Вудк|Вудочк|Вудилищ|Удилищ|Фідер|Пікер|Мах)", re.I)
F_RE = {f: re.compile(r"name='names\[i18n\]\[3\]\[" + f + r"\]' value='([^']*)'")
        for f in ("test", "casting_test")}


def main() -> int:
    from horoshop_catalog import build_canonical_products
    prods = build_canonical_products()
    ids = json.load(open(ROOT / "data" / "article_id_full.json", encoding="utf-8"))
    rods = [str(p.get("article")).strip() for p in prods
            if ROD_WORD.search((p.get("title") or "").strip())]
    rods = [a for a in rods if a in ids]

    done: dict[str, dict] = {}
    if OUT.exists():
        done = json.load(open(OUT, encoding="utf-8"))
        print(f"Resume: {len(done)}", flush=True)

    env = load_env()
    base = get_base_url(env)
    s = requests.Session()
    s.headers["User-Agent"] = "fish-sync-rod-crawl/1.0"
    auth(s, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    for i, art in enumerate(rods, 1):
        if art in done:
            continue
        try:
            r = s.get(f"{base}/adminLegacy/edit.php",
                      params={"id": ids[art], "handler": "381", "checkcode": "yamete_kudasai"},
                      timeout=30, verify=False)
            vals = {}
            for f, rx in F_RE.items():
                m = rx.search(r.text)
                vals[f] = m.group(1).strip() if m else None
            done[art] = vals
        except Exception as exc:
            done[art] = {"err": str(exc)[:100]}
        if len(done) % 50 == 0:
            json.dump(done, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"[{len(done)}/{len(rods)}]", flush=True)
        time.sleep(1.2)

    json.dump(done, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    dups = sum(1 for v in done.values()
               if v.get("test") and v.get("casting_test")
               and v["test"].replace(" г", "").strip() == v["casting_test"].replace(" г", "").strip())
    print(f"ГОТОВО: {len(done)} вудилищ, дублів test==casting_test: {dups}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
