"""
Превʼю категорій v2 (2026-06-10): красиві, УНІКАЛЬНІ, релевантні.

Джерела (у порядку пріоритету), глобальна унікальність фото між категоріями:
  1. Клієнтський архів F:\\FISH_IMAGES\\_extracted (точні збіги за назвою категорії)
  2. public/family-photo-pool/{family}/ — чисті реальні фото типу товару
     (family визначається через detect_family(назва категорії))
  3. Поточний asset категорії (фолбек, лишається як був)

Ключі нові: cat_real2_* → CSS отримує нові URL (кеш ламається автоматично).
Після прогону: python src\\generate_brand_overrides.py && python src\\push_horoshop_client_css.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

from build_all_unique_category_previews import (  # noqa: E402
    fetch_slug_titles,
    load_env,
    load_inventory,
    title_from_slug,
)
from build_real_category_previews import (  # noqa: E402
    admin_login,
    render_real_preview,
    upload_asset,
)
from catalog_rules import detect_family  # noqa: E402

REPORT = ROOT / "data" / "horoshop_category_visuals_report.json"
OUT_DIR = ROOT / "public" / "site-category-assets-v2"
POOL_DIR = ROOT / "public" / "family-photo-pool"

# сім'я-фолбек, якщо у пулі мало/нема фото
FAMILY_FALLBACK = {
    "bait_mix": "groundbait",
    "liquid_attractant": "groundbait",
    "pop_up_bait": "boilie",
    "pellets": "grain_bait",
    "foam_paste": "groundbait",
    "shock_leader": "line",
    "fluorocarbon": "line",
    "ready_leader": "rigging",
    "rigging": "swivel",
    "rod_rest_accessory": "bite_indicator",
    "other": "tools",
}


def keywords_match(tokens: str, title: str) -> int:
    score = 0
    for w in re.findall(r"[а-яіїєґa-z0-9]{4,}", title.lower()):
        if w in tokens.lower():
            score += 1
    return score


def main() -> int:
    env = load_env()
    base_url = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    category_map = dict(report.get("category_map") or {})
    uploads = report.setdefault("uploads", {})
    slugs = sorted(category_map.keys())

    titles = fetch_slug_titles(base_url)
    inventory = load_inventory()
    print(f"категорій: {len(slugs)} | архівних фото: {len(inventory)}")

    # пул фото по сім'ях
    pool: dict[str, list[Path]] = {}
    for fam_dir in POOL_DIR.iterdir() if POOL_DIR.exists() else []:
        if fam_dir.is_dir():
            pool[fam_dir.name] = sorted(p for p in fam_dir.iterdir()
                                        if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))

    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-category-previews-v2/1.0"
    admin_login(session, base_url, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    used: set[str] = set()
    prepared: dict[str, dict] = {}
    stats = {"archive": 0, "pool": 0, "kept_old": 0}

    # 1-й прохід: архівні точні збіги (найцінніші)
    archive_pick: dict[str, Path] = {}
    for slug in slugs:
        title = title_from_slug(slug, titles)
        best, best_score = None, 1
        for row in inventory:
            if row["abs_path"] in used:
                continue
            sc = keywords_match(row["tokens"], title)
            if sc > best_score:
                best, best_score = row, sc
        if best:
            archive_pick[slug] = Path(best["abs_path"])
            used.add(best["abs_path"])

    for slug in slugs:
        title = title_from_slug(slug, titles)
        key = "cat_real2_" + re.sub(r"[^a-z0-9]+", "_", slug.strip("/")).strip("_")
        source: Path | None = None
        source_type = ""

        if slug in archive_pick:
            source, source_type = archive_pick[slug], "archive"
        else:
            fam = detect_family(title)
            tried = [fam, FAMILY_FALLBACK.get(fam, ""), "tools"]
            for f in tried:
                for cand in pool.get(f, []):
                    if str(cand) not in used:
                        source, source_type = cand, f"pool:{f}"
                        break
                if source:
                    break

        if not source:
            stats["kept_old"] += 1
            continue  # лишаємо старий asset

        used.add(str(source))
        target = OUT_DIR / f"{key}.jpg"
        try:
            render_real_preview(source, target, slug)
            uploads[key] = upload_asset(session, base_url, target)
            category_map[slug] = key
            prepared[key] = {"slug": slug, "title": title, "source_type": source_type,
                             "source": str(source), "uri": uploads[key]["uri"]}
            stats["archive" if source_type == "archive" else "pool"] += 1
        except Exception as exc:
            print(f"  FAIL {slug}: {str(exc)[:100]}")

        if len(prepared) % 20 == 0:
            print(f"  ...{len(prepared)} готово")

    report["category_map"] = category_map
    report["previews_v2"] = {"count": len(prepared), "stats": stats, "prepared": prepared}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ГОТОВО: {len(prepared)} нових превʼю | {stats}")
    return 0


if __name__ == "__main__":
    sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
