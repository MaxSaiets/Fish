"""
Створення 629 товарів, які відсутні на сайті (артикули з провідними нулями —
pricelist-імпортер їх відкидає на сервері). Шлях: legacy-форма addnew (handler=381).

  python src\\create_missing_products_by_form.py --limit 1    # тест
  python src\\create_missing_products_by_form.py              # всі
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

from apply_horoshop_menu_fixes import LegacyFormParser, auth, get_base_url, load_env, post_form  # noqa: E402
from sync_content_playwright import build_product_seo  # noqa: E402
from update_created_products import load_alias_map  # noqa: E402

PRESENCE = {"В наявності": "1", "Немає в наявності": "2"}
THROTTLE_SEC = 1.2  # жорсткий rate-limit: ≤1 товар/сек (вимога після листа Horoshop)


def build_path_map() -> dict[str, str]:
    tree = json.loads((ROOT / "data" / "category_tree_site.json").read_text(encoding="utf-8"))
    byid = {c["id"]: c for c in tree}

    def full_path(c) -> str:
        parts = [c["title"]]
        p = c["parent"]
        while p in byid:
            parts.append(byid[p]["title"])
            p = byid[p]["parent"]
        return " / ".join(reversed(parts))

    out: dict[str, str] = {}
    for c in tree:
        out[full_path(c).casefold()] = c["id"]
    # додатково: лиф-назва → id (фолбек), тільки якщо унікальна
    leaf_count: dict[str, int] = {}
    for c in tree:
        leaf_count[c["title"].casefold()] = leaf_count.get(c["title"].casefold(), 0) + 1
    for c in tree:
        t = c["title"].casefold()
        if leaf_count[t] == 1:
            out.setdefault("leaf:" + t, c["id"])
    return out


def build_tree_index():
    tree = json.loads((ROOT / "data" / "category_tree_site.json").read_text(encoding="utf-8"))
    byid = {c["id"]: c for c in tree}
    children: dict[str, list[dict]] = {}
    for c in tree:
        children.setdefault(c["parent"], []).append(c)
    return tree, byid, children


_TREE, _BYID, _CHILDREN = build_tree_index()


SEGMENT_ALIASES = {
    "сані": "Сани та ящики",
    "одяг та взуття": "Одяг та взуття",
}


def resolve_category(parent_path: str, path_map: dict[str, str]) -> str | None:
    import difflib
    cp = parent_path.casefold()
    if cp in path_map:
        return path_map[cp]
    parts = [s.strip() for s in parent_path.split(" / ") if s.strip()]
    # "X / всі" → сама категорія X
    parts = [SEGMENT_ALIASES.get(s.casefold(), s) for s in parts if s.casefold() != "всі"]
    # пошук по дереву рівень за рівнем: точний збіг або fuzzy серед дітей
    node_id = "97"
    for part in parts:
        kids = _CHILDREN.get(node_id, [])
        if not kids:
            return None
        titles = [k["title"] for k in kids]
        exact = next((k for k in kids if k["title"].casefold() == part.casefold()), None)
        if exact:
            node_id = exact["id"]
            continue
        match = difflib.get_close_matches(part, titles, n=1, cutoff=0.55)
        if match:
            node_id = next(k["id"] for k in kids if k["title"] == match[0])
            continue
        # частковий вміст (перейменування типу "вудилища" -> "Вудилища махові")
        contains = [k for k in kids if part.casefold() in k["title"].casefold()
                    or k["title"].casefold() in part.casefold()]
        if len(contains) == 1:
            node_id = contains[0]["id"]
            continue
        # дитину не знайдено — кладемо у найглибшого знайденого предка
        break
    return node_id if node_id != "97" else None


def create_product(session, base_url: str, cp: dict, cat_id: str, alias_map: dict | None = None) -> None:
    url = (f"{base_url}/adminLegacy/edit.php?id=addnew&parent={cat_id}"
           f"&handler=381&checkcode=yamete_kudasai&showPages")
    r = session.get(url, timeout=60, verify=False)
    r.raise_for_status()
    p = LegacyFormParser()
    p.feed(r.text)
    # для НОВОГО запису всі порожні поля викидаємо: відсутність = NULL/дефолт,
    # а порожній рядок у FK-селектах (installments, supplier_id...) валить INSERT
    payload = {k: v for k, v in p.fields.items() if str(v) != ""}

    title = str(cp["title"]).strip()
    seo_t, seo_d = build_product_seo(title, cp.get("price"))
    payload.update({
        "checkcode": "yamete_kudasai",
        "id": "addnew",
        "handler": "381",
        "handlertable": "h_product_characteristics",
        "back": "index.php",
        "parent_common[parent]": cat_id,
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
    # характеристики одразу при створенні (нуль додаткових запитів)
    if alias_map:
        for prm in cp.get("params") or []:
            alias = alias_map.get(str(prm.get("name", "")).strip().casefold())
            val = str(prm.get("value", "")).strip()
            if alias and val:
                payload[f"names[i18n][3][{alias}]"] = val
    import time
    last = None
    for attempt in range(4):
        try:
            resp = post_form(session, f"{base_url}/adminLegacy/save.php", payload,
                             f"{base_url}/adminLegacy/edit.php?id=addnew&parent={cat_id}&handler=381")
            resp.raise_for_status()
            body = resp.text[:500]
            if '"HTTP_ERROR"' in body or "Integrity constraint" in body:
                raise RuntimeError(f"save error: {body[:180]}")
            return
        except Exception as exc:  # RemoteDisconnected тощо — задокументований транзієнт
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise last


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--source-diff", action="store_true",
                    help="список = нові товари з data/db_diff_20260701.json")
    args = ap.parse_args()

    # джерело списку: --source diff (нові з бази 01.07) або unaddressable (стара хвиля)
    src_file = ROOT / "data" / ("db_diff_20260701.json" if "--source-diff" in sys.argv else "unaddressable_articles_20260610.json")
    raw = json.loads(src_file.read_text(encoding="utf-8"))
    una = raw.get("added") or raw.get("unaddressable") or []
    from horoshop_catalog import build_canonical_products
    products = {str(p["article"]).strip(): p for p in build_canonical_products()}
    path_map = build_path_map()
    alias_map = load_alias_map()

    env = load_env()
    base = get_base_url(env)
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-create-missing/1.0"
    auth(session, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    progress_path = ROOT / "data" / "created_missing_progress.json"
    created: set[str] = set(json.loads(progress_path.read_text(encoding="utf-8"))) if progress_path.exists() else set()

    todo = [a for a in una if a in products and a not in created]
    if args.limit:
        todo = todo[: args.limit]
    print(f"створюємо: {len(todo)} (вже створено: {len(created)})", flush=True)

    report = {"started": datetime.now().isoformat(), "ok": 0, "no_category": [], "failed": []}
    for i, art in enumerate(todo, 1):
        cp = products[art]
        cat_id = resolve_category(str(cp.get("parent") or ""), path_map)
        if not cat_id:
            report["no_category"].append({"article": art, "parent": cp.get("parent")})
            continue
        try:
            import time as _t
            create_product(session, base, cp, cat_id, alias_map=alias_map)
            _t.sleep(THROTTLE_SEC)
            report["ok"] += 1
            created.add(art)
            if report["ok"] % 10 == 0:
                progress_path.write_text(json.dumps(sorted(created), ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            report["failed"].append({"article": art, "error": str(exc)[:140]})
        if i % 25 == 0 or i == len(todo):
            print(f"[{i}/{len(todo)}] ok={report['ok']} no_cat={len(report['no_category'])} fail={len(report['failed'])}", flush=True)

    progress_path.write_text(json.dumps(sorted(created), ensure_ascii=False), encoding="utf-8")
    report["finished"] = datetime.now().isoformat()
    out = ROOT / "data" / f"create_missing_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Звіт: {out}")
    return 0


if __name__ == "__main__":
    sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.exit(main())
