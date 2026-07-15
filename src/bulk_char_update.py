"""
Варіант 1: масове оновлення ХАРАКТЕРИСТИК товарів через форму (edit.php→save.php).
Єдиний робочий канал (pricelist/YML характеристики не несуть — перевірено).

Безпека від бану:
  - 1 потік, пауза THROTTLE між товарами (за замовч. 2.0с → 0.5 req/s, 40× під порогом Horoshop);
  - resumable: чекпойнт data/bulk_char_progress.json;
  - in-stock товари ПЕРШИМИ (найцінніші).

Записує лише характеристики, назви яких є в шаблоні 381 (мапа alias).
Не чіпає інші поля (порожні відкидаються, наявні лишаються).

  python src\\bulk_char_update.py --limit 5      # тест
  python src\\bulk_char_update.py --in-stock-only
  python src\\bulk_char_update.py                # усі з відомим id
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

PROGRESS = ROOT / "data" / "bulk_char_progress.json"
ID_MAP_FILES = [ROOT / "data" / "article_id_full.json",
                ROOT / "data" / "article_to_internal_id_20260610.json",
                ROOT / "data" / "unaddressable_id_map_20260610.json"]


def load_alias_map() -> dict[str, str]:
    data = json.loads((ROOT / "data" / "admin_template_381_params_20260607.json").read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for p in data.get("params", []):
        cells = p.get("cells") or []
        if len(cells) >= 2 and cells[0] and cells[1]:
            out[str(cells[0]).strip().casefold()] = str(cells[1]).strip()
    return out


def load_id_map() -> dict[str, str]:
    m: dict[str, str] = {}
    for f in ID_MAP_FILES:
        if f.exists():
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                for a, i in d.items():
                    m.setdefault(str(a).strip(), str(i))
            except Exception:
                pass
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--in-stock-only", action="store_true")
    ap.add_argument("--max-id", type=int, default=None,
                    help="обробляти лише товари з internal_id < N (пропустити створені 503)")
    ap.add_argument("--throttle", type=float, default=2.0)
    args = ap.parse_args()

    from horoshop_catalog import build_canonical_products
    products = {str(p["article"]).strip(): p for p in build_canonical_products()}
    id_map = load_id_map()
    alias_map = load_alias_map()
    done: set[str] = set(json.loads(PROGRESS.read_text(encoding="utf-8"))) if PROGRESS.exists() else set()

    # черга: спершу in-stock, потім решта; тільки з відомим id і ще не оброблені
    def in_stock(p):
        return p.get("quantity", 0) and int(p.get("quantity") or 0) > 0
    candidates = [a for a in products if a in id_map and a not in done]
    if args.max_id:
        candidates = [a for a in candidates if str(id_map[a]).isdigit() and int(id_map[a]) < args.max_id]
    candidates.sort(key=lambda a: (0 if in_stock(products[a]) else 1, a))
    if args.in_stock_only:
        candidates = [a for a in candidates if in_stock(products[a])]
    if args.limit:
        candidates = candidates[: args.limit]

    total = len(candidates)
    print(f"до оновлення: {total} (мапа id: {len(id_map)}, вже готово: {len(done)}, throttle {args.throttle}с)", flush=True)
    if not total:
        print("нема кандидатів (потрібна мапа id — запусти tmp/crawl_ids_full.py)", flush=True)
        return 0

    env = load_env()
    base = get_base_url(env)
    s = requests.Session()
    s.headers["User-Agent"] = "fish-sync-char-update/1.0"
    auth(s, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    report = {"started": datetime.now().isoformat(), "ok": 0, "chars_set": 0, "skipped": [], "failed": []}
    for i, art in enumerate(candidates, 1):
        cp = products[art]
        pid = id_map[art]
        try:
            url = (f"{base}/adminLegacy/edit.php?id={pid}&parent=97"
                   f"&action=edit&handler=381&checkcode=yamete_kudasai")
            r = s.get(url, timeout=60, verify=False)
            r.raise_for_status()
            p = LegacyFormParser()
            p.feed(r.text)
            f = dict(p.fields)
            # перевірка відповідності артикула (безпека — не редагуємо чужий товар)
            if str(f.get("modifications[0][article]", "")).strip() != art:
                report["skipped"].append({"article": art, "id": pid, "reason": "article mismatch"})
                continue
            payload = {k: v for k, v in f.items() if str(v) != ""}
            payload.update({
                "checkcode": "yamete_kudasai", "id": pid, "handler": "381",
                "handlertable": "h_product_characteristics", "back": "index.php",
            })
            n_set = 0
            for prm in cp.get("params") or []:
                alias = alias_map.get(str(prm.get("name", "")).strip().casefold())
                val = str(prm.get("value", "")).strip()
                if alias and val:
                    payload[f"names[i18n][3][{alias}]"] = val
                    n_set += 1
            if n_set == 0:
                report["skipped"].append({"article": art, "reason": "no mappable params"})
                done.add(art)
                continue
            last = None
            for attempt in range(3):
                try:
                    resp = post_form(s, f"{base}/adminLegacy/save.php", payload, url)
                    resp.raise_for_status()
                    if "HTTP_ERROR" in resp.text[:400]:
                        raise RuntimeError(resp.text[:150])
                    break
                except Exception as exc:
                    last = exc
                    time.sleep(3 * (attempt + 1))
            else:
                raise last
            report["ok"] += 1
            report["chars_set"] += n_set
            done.add(art)
        except Exception as exc:
            report["failed"].append({"article": art, "id": pid, "error": str(exc)[:140]})
        time.sleep(args.throttle)
        if i % 25 == 0 or i == total:
            PROGRESS.write_text(json.dumps(sorted(done), ensure_ascii=False), encoding="utf-8")
            print(f"[{i}/{total}] ok={report['ok']} chars={report['chars_set']} "
                  f"skip={len(report['skipped'])} fail={len(report['failed'])}", flush=True)

    PROGRESS.write_text(json.dumps(sorted(done), ensure_ascii=False), encoding="utf-8")
    report["finished"] = datetime.now().isoformat()
    out = ROOT / "data" / f"bulk_char_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Звіт: {out} | ok={report['ok']} chars_set={report['chars_set']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.exit(main())
