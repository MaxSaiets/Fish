"""
Догрузка ПОВНОГО набору характеристик на СТВОРЕНІ товари (edit.php GET=503).

Канал: пересейв через blank-scaffold (id=addnew) з націленням id=<реальний>.
Той самий payload, що й при створенні (title/desc/seo/price/presence/chars),
БЕЗ полів галереї → фото не має чіпатись. РИЗИК все одно є → спершу --test.

  python src/created_products_enrich.py --list            # показати створені (503) товари
  python src/created_products_enrich.py --test <артикул>  # оновити 1, вивести до/після для звірки
  python src/created_products_enrich.py --apply           # масово (throttle), resumable

Резюме: data/created_enrich_progress.json
"""
from __future__ import annotations

import argparse
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

from apply_horoshop_menu_fixes import LegacyFormParser, auth, get_base_url, load_env, post_form  # noqa: E402
from create_missing_products_by_form import PRESENCE, build_product_seo  # noqa: E402
from bulk_char_update import load_alias_map, load_id_map  # noqa: E402

PROGRESS = ROOT / "data" / "created_enrich_progress.json"
CAT_MAP = ROOT / "data" / "category_name_to_id.json"  # optional


def _cat_id(cp: dict) -> str:
    """id категорії товару. Якщо мапи назв→id нема — беремо root 97 (безпечний дефолт)."""
    if CAT_MAP.exists():
        m = json.loads(CAT_MAP.read_text(encoding="utf-8"))
        cid = m.get(str(cp.get("parent") or "").strip())
        if cid:
            return str(cid)
    return "97"


def build_update_payload(session, base, cp, pid, alias_map, cat_id):
    """Payload оновлення існуючого товару через addnew-scaffold, id=реальний."""
    url = (f"{base}/adminLegacy/edit.php?id=addnew&parent={cat_id}"
           f"&handler=381&checkcode=yamete_kudasai&showPages")
    r = session.get(url, timeout=60, verify=False)
    r.raise_for_status()
    p = LegacyFormParser()
    p.feed(r.text)
    payload = {k: v for k, v in p.fields.items() if str(v) != ""}
    title = str(cp["title"]).strip()
    seo_t, seo_d = build_product_seo(title, cp.get("price"))
    payload.update({
        "checkcode": "yamete_kudasai",
        "id": str(pid),  # <-- реальний id => ОНОВЛЕННЯ, не створення
        "handler": "381",
        "handlertable": "h_product_characteristics",
        "back": "index.php",
        # НЕ шлемо parent_common[parent] — щоб НЕ перемістити товар у корінь.
        # Якщо тест покаже, що категорія губиться — повернути з коректним cat_id.
        "parent_common[i18n][3][title]": title,
        "parent_common[i18n][3][description]": cp.get("description") or "",
        "parent_common[i18n][3][seo_title]": seo_t,
        "parent_common[i18n][3][seo_description]": seo_d,
        "modifications[0][article]": str(cp["article"]).strip(),
        "modifications[0][i18n][3][mod_title]": title,
        "modifications[0][price]": str(cp.get("price") or 0),
        "modifications[0][currency]": "1",
        "modifications[0][presence]": PRESENCE.get(str(cp.get("presence") or ""), "2"),
        "modifications[0][display_in_showcase]": "1",
    })
    n = 0
    for prm in cp.get("params") or []:
        alias = alias_map.get(str(prm.get("name", "")).strip().casefold())
        val = str(prm.get("value", "")).strip()
        if alias and val:
            payload[f"names[i18n][3][{alias}]"] = val
            n += 1
    return payload, url, n


def is_created(session, base, pid) -> bool:
    """503 на edit.php GET = створений (недосяжний старою формою)."""
    try:
        r = session.get(f"{base}/adminLegacy/edit.php?id={pid}&parent=97&action=edit"
                        f"&handler=381&checkcode=yamete_kudasai", timeout=40, verify=False)
        return r.status_code == 503 or "modifications[0]" not in r.text
    except Exception:
        return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--test", metavar="ARTICLE")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--throttle", type=float, default=2.0)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    from horoshop_catalog import build_canonical_products
    products = {str(p["article"]).strip(): p for p in build_canonical_products()}
    id_map = load_id_map()
    alias_map = load_alias_map()
    done = set(json.loads(PROGRESS.read_text(encoding="utf-8"))) if PROGRESS.exists() else set()

    env = load_env()
    base = get_base_url(env)
    s = requests.Session()
    s.headers["User-Agent"] = "fish-created-enrich/1.0"
    auth(s, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    if args.test:
        art = args.test.strip()
        cp = products.get(art)
        pid = id_map.get(art)
        if not cp or not pid:
            print("нема такого артикула/id"); return 1
        cat = _cat_id(cp)
        payload, url, n = build_update_payload(s, base, cp, pid, alias_map, cat)
        print(f"ТЕСТ {art} id{pid} cat{cat}: у payload {n} характеристик, {len(payload)} полів")
        print("Ключові поля:", {k: payload[k] for k in list(payload) if k.startswith(('id','modifications[0][article]','parent_common[parent]'))})
        resp = post_form(s, f"{base}/adminLegacy/save.php", payload, url)
        print("save status:", resp.status_code, "| body:", resp.text[:160].replace("\n", " "))
        print(">>> ТЕПЕР ЗВІР НА ВІТРИНІ: назва/ціна/ФОТО збереглись, характеристик побільшало, немає дубля модифікації.")
        return 0

    # список створених (503)
    candidates = [a for a in products if a in id_map and a not in done]
    if args.list or args.apply:
        created = []
        for a in candidates:
            if is_created(s, base, id_map[a]):
                created.append(a)
            if args.list and len(created) >= 40:
                break
            time.sleep(0.4)
        print(f"створених (503) серед незалитих: {len(created)}{' (показано перші)' if args.list else ''}")
        for a in created[:20]:
            print("  ", a, id_map[a], str(products[a].get('title',''))[:45])
        if not args.apply:
            return 0

        report = {"ok": 0, "fail": []}
        todo = created[: args.limit] if args.limit else created
        for i, art in enumerate(todo, 1):
            cp = products[art]; pid = id_map[art]; cat = _cat_id(cp)
            try:
                payload, url, n = build_update_payload(s, base, cp, pid, alias_map, cat)
                resp = post_form(s, f"{base}/adminLegacy/save.php", payload, url)
                resp.raise_for_status()
                if "HTTP_ERROR" in resp.text[:400] or "Integrity constraint" in resp.text[:400]:
                    raise RuntimeError(resp.text[:150])
                report["ok"] += 1
                done.add(art)
            except Exception as exc:
                report["fail"].append({"article": art, "error": str(exc)[:120]})
            time.sleep(args.throttle)
            if i % 25 == 0 or i == len(todo):
                PROGRESS.write_text(json.dumps(sorted(done), ensure_ascii=False), encoding="utf-8")
                print(f"[{i}/{len(todo)}] ok={report['ok']} fail={len(report['fail'])}", flush=True)
        PROGRESS.write_text(json.dumps(sorted(done), ensure_ascii=False), encoding="utf-8")
        print("ГОТОВО:", report["ok"], "оновлено, fail", len(report["fail"]))
        return 0

    print("вкажи --list | --test <арт> | --apply")
    return 0


if __name__ == "__main__":
    sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.exit(main())
