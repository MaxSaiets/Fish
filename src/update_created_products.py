"""
Оновлення 629 створених товарів (нульові артикули) через форму:
ціна + наявність + ХАРАКТЕРИСТИКИ (поля names[i18n][3][alias] шаблону 381).

Це і є form-шлях підтримки залишків для товарів, яких не бачить pricelist.
Запускати після кожної зміни залишків (або щодня планувальником):

  python src\\update_created_products.py --limit 2     # тест
  python src\\update_created_products.py               # всі з мапи
  python src\\update_created_products.py --stock-only  # лише ціна/наявність (швидше)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

from apply_horoshop_menu_fixes import LegacyFormParser, auth, get_base_url, load_env, post_form  # noqa: E402

PRESENCE = {"В наявності": "1", "Немає в наявності": "2"}
MAP_PATH = ROOT / "data" / "unaddressable_id_map_20260610.json"


def load_alias_map() -> dict[str, str]:
    data = json.loads((ROOT / "data" / "admin_template_381_params_20260607.json").read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for p in data.get("params", []):
        cells = p.get("cells") or []
        if len(cells) >= 2 and cells[0] and cells[1]:
            out[str(cells[0]).strip().casefold()] = str(cells[1]).strip()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--stock-only", action="store_true")
    args = ap.parse_args()

    id_map: dict[str, str] = json.loads(MAP_PATH.read_text(encoding="utf-8")) if MAP_PATH.exists() else {}
    if not id_map:
        print("мапа порожня — спершу tmp/probe_id_range.py")
        return 1

    from horoshop_catalog import build_canonical_products
    products = {str(p["article"]).strip(): p for p in build_canonical_products()}
    alias_map = load_alias_map()

    env = load_env()
    base = get_base_url(env)
    s = requests.Session()
    s.headers["User-Agent"] = "fish-sync-update-created/1.0"
    auth(s, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    todo = [(a, pid) for a, pid in id_map.items() if a in products]
    if args.limit:
        todo = todo[: args.limit]
    print(f"оновлюємо: {len(todo)} (характеристики: {'ні' if args.stock_only else 'так'})", flush=True)

    report = {"started": datetime.now().isoformat(), "ok": 0, "failed": [], "params_set": 0}
    for i, (art, pid) in enumerate(todo, 1):
        cp = products[art]
        try:
            r = s.get(f"{base}/adminLegacy/edit.php?id={pid}&parent=97&action=edit&handler=381&checkcode=yamete_kudasai",
                      timeout=60, verify=False)
            r.raise_for_status()
            p = LegacyFormParser()
            p.feed(r.text)
            form_art = str(p.fields.get("modifications[0][article]", "")).strip()
            if form_art != art:
                report["failed"].append({"article": art, "id": pid, "error": f"article mismatch: {form_art}"})
                continue
            payload = {k: v for k, v in p.fields.items() if str(v) != ""}
            payload.update({
                "checkcode": "yamete_kudasai", "id": pid, "handler": "381",
                "handlertable": "h_product_characteristics", "back": "index.php",
                "modifications[0][price]": str(cp.get("price") or 0),
                "modifications[0][presence]": PRESENCE.get(str(cp.get("presence") or ""), "2"),
            })
            if not args.stock_only:
                for prm in cp.get("params") or []:
                    alias = alias_map.get(str(prm.get("name", "")).strip().casefold())
                    val = str(prm.get("value", "")).strip()
                    if alias and val:
                        payload[f"names[i18n][3][{alias}]"] = val
                        report["params_set"] += 1
            last = None
            for attempt in range(4):
                try:
                    resp = post_form(s, f"{base}/adminLegacy/save.php", payload,
                                     f"{base}/adminLegacy/edit.php?id={pid}&handler=381")
                    resp.raise_for_status()
                    if '"HTTP_ERROR"' in resp.text[:400]:
                        raise RuntimeError(resp.text[:160])
                    break
                except Exception as exc:
                    last = exc
                    time.sleep(1.5 * (attempt + 1))
            else:
                raise last
            report["ok"] += 1
        except Exception as exc:
            report["failed"].append({"article": art, "id": pid, "error": str(exc)[:140]})
        if i % 25 == 0 or i == len(todo):
            print(f"[{i}/{len(todo)}] ok={report['ok']} fail={len(report['failed'])} params={report['params_set']}", flush=True)

    report["finished"] = datetime.now().isoformat()
    out = ROOT / "data" / f"update_created_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Звіт: {out}")
    return 0


if __name__ == "__main__":
    sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.exit(main())
