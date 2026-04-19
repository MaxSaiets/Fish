"""
Імпортує фотографії товарів з папки Олени (~20GB файлів) у локальне сховище
public/photos/ і прописує URL-и в meta_store.variants.pictures_json.

Стратегія мепингу filename → kod:
  1. **Точний artikul**: regex (\d{2,7}) у назві файлу — перевіряємо проти всіх kods.
     Файли: "302.jpg", "302_1.jpg", "302-front.png", "img_302_main.JPG"
  2. **Префіксний матч по моделі**: якщо artikul не знайдено, fuzzy-match назви файлу
     проти display_name парент-моделі через rapidfuzz (поріг 75) → присвоюється всім
     варіантам моделі.
  3. **Manual map**: data/photo_overrides.json для крайових випадків.

Кожен файл копіюється у public/photos/{kod}/{seq}.jpg, де seq = порядковий номер 1..N.
URL-форма: {PUBLIC_BASE_URL}/photos/{kod}/{seq}.jpg.

Запуск:
  python src/photo_sync.py --src "D:/Olena/photos" --dry-run
  python src/photo_sync.py --src "D:/Olena/photos"
  python src/photo_sync.py --simulate     # використати fixture-папку для тесту
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path

try:
    from rapidfuzz import fuzz
    HAS_FUZZ = True
except ImportError:
    HAS_FUZZ = False

from dotenv import load_dotenv

ROOT = Path(r"D:\FISH\fish-sync")
META_DB = ROOT / "data" / "meta_store.sqlite"
PUBLIC_PHOTOS = ROOT / "public" / "photos"
FIXTURE_DIR = ROOT / "fixtures" / "photos"
OVERRIDES_JSON = ROOT / "data" / "photo_overrides.json"

load_dotenv(ROOT / ".env")
PUBLIC_BASE = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8080")

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
KOD_RE = re.compile(r"(?<!\d)(\d{2,7})(?!\d)")
# Артикули з крапками типу "1693.06.07"
KOD_DOTTED_RE = re.compile(r"(\d{2,5}(?:\.\d{1,3}){1,4})")
FUZZ_THRESHOLD = 75


def load_index(conn: sqlite3.Connection) -> tuple[dict[str, str], dict[str, list[str]]]:
    """
    Returns:
      kod_set:   {kod: parent_key}
      model_idx: {parent_key: {display_name, [kods]}}
    """
    rows = conn.execute(
        """
        SELECT v.kod, v.parent_key, m.display_name
        FROM variants v JOIN models m ON m.parent_key = v.parent_key
        """
    ).fetchall()
    kod_to_parent = {}
    model_kods: dict[str, dict] = {}
    for r in rows:
        kod, pk, dn = r
        kod_to_parent[kod] = pk
        model_kods.setdefault(pk, {"display_name": dn, "kods": []})["kods"].append(kod)
    return kod_to_parent, model_kods


def load_overrides() -> dict[str, str]:
    if OVERRIDES_JSON.exists():
        return json.loads(OVERRIDES_JSON.read_text(encoding="utf-8"))
    return {}


def match_file(
    filepath: Path,
    kod_to_parent: dict[str, str],
    model_kods: dict[str, dict],
    overrides: dict[str, str],
) -> list[str]:
    """Повертає список kods, до яких належить фото."""
    name = filepath.stem
    # 0. manual override
    if filepath.name in overrides:
        return [overrides[filepath.name]]
    # 1a. цілий stem як kod (точний матч "302.jpg" → "302")
    if name in kod_to_parent:
        return [name]
    # 1a.bis: stem без trailing "_N" / "-N" суфіксу ("Y-5040-240_1" → "Y-5040-240")
    no_suffix = re.sub(r"[_\s](\d{1,3})$", "", name)
    if no_suffix != name and no_suffix in kod_to_parent:
        return [no_suffix]
    # 1b. артикули з крапками (1693.06.07)
    for m in KOD_DOTTED_RE.finditer(name):
        if m.group(1) in kod_to_parent:
            return [m.group(1)]
    # 1c. суфіксний trim (302_1, 302-front)
    stripped = re.split(r"[_\-\s]", name, maxsplit=1)[0]
    if stripped in kod_to_parent:
        return [stripped]
    # 1d. чисто цифровий artikul
    for m in KOD_RE.finditer(name):
        candidate = m.group(1)
        if candidate in kod_to_parent:
            return [candidate]
    # 2. fuzzy match against model display_name → assign to all variants
    if HAS_FUZZ:
        best_pk, best_score = None, 0
        # очищаємо назву файлу від службових слів
        clean = re.sub(r"[_\-]+", " ", name).strip()
        for pk, info in model_kods.items():
            score = fuzz.partial_ratio(clean.lower(), info["display_name"].lower())
            if score > best_score:
                best_pk, best_score = pk, score
        if best_score >= FUZZ_THRESHOLD and best_pk:
            return model_kods[best_pk]["kods"]
    return []


def copy_and_register(
    filepath: Path,
    kods: list[str],
    seq_per_kod: dict[str, int],
    dry_run: bool,
) -> list[tuple[str, str]]:
    """Копіює файл, повертає [(kod, url), ...]."""
    out = []
    ext = filepath.suffix.lower()
    if ext == ".jpeg":
        ext = ".jpg"
    for kod in kods:
        seq = seq_per_kod.get(kod, 0) + 1
        seq_per_kod[kod] = seq
        dest = PUBLIC_PHOTOS / kod / f"{seq}{ext}"
        url = f"{PUBLIC_BASE}/photos/{kod}/{seq}{ext}"
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(filepath, dest)
        out.append((kod, url))
    return out


def update_meta(conn: sqlite3.Connection, kod_to_urls: dict[str, list[str]]) -> int:
    n = 0
    for kod, urls in kod_to_urls.items():
        conn.execute(
            "UPDATE variants SET pictures_json = ? WHERE kod = ?",
            (json.dumps(urls, ensure_ascii=False), kod),
        )
        n += 1
    conn.commit()
    return n


def sync_folder(src: Path, dry_run: bool = False, clear: bool = False) -> dict:
    if not src.exists():
        sys.exit(f"Source folder not found: {src}")

    conn = sqlite3.connect(META_DB)
    kod_to_parent, model_kods = load_index(conn)
    overrides = load_overrides()

    if clear and not dry_run:
        if PUBLIC_PHOTOS.exists():
            shutil.rmtree(PUBLIC_PHOTOS)
        # Скинути pictures_json
        conn.execute("UPDATE variants SET pictures_json = '[]'")
        conn.commit()

    files = [f for f in src.rglob("*") if f.is_file() and f.suffix.lower() in ALLOWED_EXT]
    print(f"Scanning {len(files)} files in {src}...")

    kod_to_urls: dict[str, list[str]] = {}
    seq_per_kod: dict[str, int] = {}
    matched = unmatched = 0
    unmatched_samples: list[str] = []

    for f in files:
        kods = match_file(f, kod_to_parent, model_kods, overrides)
        if not kods:
            unmatched += 1
            if len(unmatched_samples) < 10:
                unmatched_samples.append(f.name)
            continue
        results = copy_and_register(f, kods, seq_per_kod, dry_run)
        for kod, url in results:
            kod_to_urls.setdefault(kod, []).append(url)
        matched += 1

    written = 0
    if not dry_run and kod_to_urls:
        written = update_meta(conn, kod_to_urls)

    conn.close()

    summary = {
        "scanned": len(files),
        "matched_files": matched,
        "unmatched_files": unmatched,
        "kods_with_photos": len(kod_to_urls),
        "total_kods_in_db": len(kod_to_parent),
        "coverage_pct": round(100 * len(kod_to_urls) / max(len(kod_to_parent), 1), 1),
        "rows_updated": written,
        "unmatched_samples": unmatched_samples,
        "dry_run": dry_run,
    }
    return summary


def make_fixture() -> None:
    """
    Створює симульовану папку Олени з невеликими jpg-плейсхолдерами,
    імітуючи реальну структуру наіменування файлів.
    """
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    # 1x1 white JPEG
    JPEG_1PX = bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707"
        "07090908"  + "0a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c2024"
        "2e2722282c372a2c30303034343f3a3a3e3a36363a36"
        "ffc0000b08000100010101011100ffc4001f000001050101010101010000000000"
        "000000010203040506070809"  + "0a0bffc40031100002010303020403040705040400000102"
        "031104052131410612516107711322328108143242a191b1c109233352f0156272"
        "d1ffda0008010100003f00fb"  + "00ffd9"
    )
    # Створимо файли для частини kods з варіантами назв
    conn = sqlite3.connect(META_DB)
    rows = conn.execute("SELECT kod, name_raw FROM variants LIMIT 30").fetchall()
    conn.close()
    naming_variants = ["{kod}.jpg", "{kod}_1.jpg", "{kod}_2.jpg", "img_{kod}.jpg"]
    n = 0
    for kod, _name in rows:
        for tmpl in naming_variants[:2]:  # 2 фото на товар
            fname = tmpl.format(kod=kod)
            (FIXTURE_DIR / fname).write_bytes(JPEG_1PX)
            n += 1
    print(f"Fixture created: {n} files in {FIXTURE_DIR}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, help="Source photos folder")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--clear", action="store_true", help="Wipe public/photos before sync")
    ap.add_argument("--simulate", action="store_true", help="Use fixture folder")
    ap.add_argument("--make-fixture", action="store_true")
    args = ap.parse_args()

    if args.make_fixture:
        make_fixture()
        return

    src = args.src
    if args.simulate:
        if not FIXTURE_DIR.exists() or not any(FIXTURE_DIR.iterdir()):
            print("Fixture empty, creating...")
            make_fixture()
        src = FIXTURE_DIR

    if not src:
        sys.exit("Provide --src or --simulate")

    summary = sync_folder(src, dry_run=args.dry_run, clear=args.clear)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
