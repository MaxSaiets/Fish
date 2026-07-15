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
import subprocess
import sys
import tempfile
import unicodedata
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
ARCHIVE_EXT = {".rar"}
KOD_RE = re.compile(r"(?<!\d)(\d{2,7})(?!\d)")
# Артикули з крапками типу "1693.06.07"
KOD_DOTTED_RE = re.compile(r"(\d{2,5}(?:\.\d{1,3}){1,4})")
FUZZ_THRESHOLD = 75
GENERIC_STOPWORDS = {
    "спінінг", "вудилище", "вудочка", "пелетс", "поп", "апи", "ап", "pop", "up",
    "прикормка", "бойли", "матеріали", "аксесуари", "карпове", "махове", "болонські",
    "bolonski", "махові", "коропове", "насадочний", "інструменти", "та", "для",
    "аксессуары", "материалы",
}
BRANDING_HINTS = {"лого", "logo", "банер", "banner"}
CATEGORY_ASSET_HINTS = {
    "категор", "category", "банер", "banner"
}
ARCHIVE_COVER_HINTS = {"обкладинка", "cover", "preview"}
SHARED_ARCHIVE_HINTS = {
    "вудилище brain apex traveller",
    "вудочка magician mifine",
    "вудочка marksman mifine",
    "вудочка бк mikado princess",
    "вудочка джокер boya bu",
    "вудочка feima premacy",
    "вудочка new hunter",
    "вудочка sport niht",
    "вудочка titan",
    "вудочка weida orion polo",
    "вудочка weida orion",
    "вудочка weida titan",
    "вудочка weida",
    "карпове вудлище kyogi",
    "спінінг kalipso navigator pro 2",
}
ARCHIVE_CONTEXT_OVERRIDES = {
    "вудилище brain apex traveller": ["1858.44.61", "1858.44.62"],
    "вудочка weida titan": ["2939", "3046", "1968", "1886"],
    "вудочка weida orion polo": ["3091", "3047", "1971"],
    "вудочка weida orion": ["4616", "4617", "4618"],
    "вудочка weida": ["2371", "1662", "1663"],
    "вудочка titan": ["4621", "4622", "4623"],
    "вудочка sport niht": ["3277", "3278"],
    "вудочка feima premacy": ["2531", "2532"],
    "вудочка new hunter": ["1877", "1880", "4084", "4095", "4071-600"],
    "вудочка джокер boya bu": ["3748", "1154", "1155", "1156", "1157"],
    "вудочка бк mikado princess": ["1235", "1236", "1237"],
    "карпове вудлище kyogi": ["1262", "1263", "1264", "1265", "4735"],
    "спінінг kalipso navigator pro 2": ["2006101", "4158", "2006103", "2368", "2369"],
}
NORMALIZE_REPLACEMENTS = {
    "3-к": "3k",
    "3 к": "3k",
    "3k baits": "3k baits",
    "robinred": "robin red",
    "krillhalibut": "krill halibut",
    "salmonstrawberry": "salmon strawberry",
    "squidoctopus": "squid octopus",
    "doube garlic": "double garlic",
    "doublegarlic": "double garlic",
    "honeystravberry": "honey strawberry",
    "tigernutcorn": "tiger nut corn",
    "pineapplepear": "pineapple pear",
    "tunaextract": "tuna extract",
    "popp up": "pop up",
    "pop-up": "pop up",
}


def load_index(conn: sqlite3.Connection) -> tuple[dict[str, str], dict[str, dict], dict[str, dict]]:
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
    variant_rows = conn.execute(
        """
        SELECT v.kod, COALESCE(NULLIF(v.name_raw, ''), m.display_name)
        FROM variants v JOIN models m ON m.parent_key = v.parent_key
        """
    ).fetchall()
    variant_index: dict[str, dict] = {}
    for kod, name in variant_rows:
        name = str(name or "")
        variant_index[kod] = {
            "name": name,
            "norm": normalize_text(name),
            "compact": compact_text(name),
            "tokens": token_set(name),
        }
    return kod_to_parent, model_kods, variant_index


def load_overrides() -> dict[str, str]:
    if OVERRIDES_JSON.exists():
        return json.loads(OVERRIDES_JSON.read_text(encoding="utf-8"))
    return {}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = value.replace("’", "'").replace("`", "'")
    value = value.replace(",", ".").replace("\\", " ").replace("/", " ")
    value = re.sub(r"(?<=[^\W\d_])(?=\d)", " ", value, flags=re.UNICODE)
    value = re.sub(r"(?<=\d)(?=[^\W\d_])", " ", value, flags=re.UNICODE)
    for src, dst in NORMALIZE_REPLACEMENTS.items():
        value = value.replace(src, dst)
    value = re.sub(r"[^\w\s\.]+", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def compact_text(value: str) -> str:
    return re.sub(r"\s+", "", normalize_text(value))


def token_set(value: str) -> set[str]:
    return {
        t for t in normalize_text(value).split()
        if len(t) > 1 and t not in GENERIC_STOPWORDS
    }


def is_branding_asset(path: Path) -> bool:
    stem = normalize_text(path.stem)
    return any(hint in stem for hint in BRANDING_HINTS)


def is_category_asset(path: Path) -> bool:
    stem = normalize_text(path.stem)
    return any(hint in stem for hint in CATEGORY_ASSET_HINTS)


def is_archive_cover_asset(path: Path) -> bool:
    stem = normalize_text(path.stem)
    return any(hint in stem for hint in ARCHIVE_COVER_HINTS)


def is_shared_archive(context: str | None) -> bool:
    if not context:
        return False
    norm = normalize_text(context)
    return any(hint in norm for hint in SHARED_ARCHIVE_HINTS)


def archive_override_kods(context: str | None) -> list[str]:
    if not context:
        return []
    norm = normalize_text(context)
    for hint, kods in ARCHIVE_CONTEXT_OVERRIDES.items():
        if hint in norm:
            return kods
    return []


def strip_image_sequence(stem: str) -> str:
    stem = re.sub(r"([,_-]\d{1,3})$", "", stem).strip()
    return stem


def has_letter(value: str) -> bool:
    return bool(re.search(r"[^\W\d_]", value, flags=re.UNICODE))


def extract_archive(archive: Path, dest_root: Path) -> Path:
    dest = dest_root / archive.stem
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["tar", "-xf", str(archive), "-C", str(dest)],
        check=True,
        capture_output=True,
        text=True,
    )
    return dest


def iter_image_sources(src: Path) -> tuple[list[dict], list[str], list[str], int, Path | None]:
    sources: list[dict] = []
    branding_assets: list[str] = []
    category_assets: list[str] = []
    archives_scanned = 0
    temp_root: Path | None = None

    ignored_dirs = {"_contact_sheets", "__macosx"}
    ignored_files = {
        "_extract_report.json",
        "_image_analysis_report.json",
        "_image_inventory.csv",
        "_archive_summary.csv",
        "_contact_sheets_report.json",
    }
    direct_files = [
        f for f in src.rglob("*")
        if f.is_file()
        and f.name.lower() not in ignored_files
        and not any(part.lower() in ignored_dirs for part in f.relative_to(src).parts[:-1])
    ]
    for f in direct_files:
        if is_branding_asset(f):
            branding_assets.append(str(f))
            continue
        if f.suffix.lower() not in ALLOWED_EXT and f.suffix.lower() != ".svg":
            continue
        if is_category_asset(f):
            category_assets.append(str(f))
            continue
        if f.suffix.lower() not in ALLOWED_EXT:
            continue
        sources.append({
            "path": f,
            "context": f.parent.name if f.parent != src else f.stem,
            "container": f.parent.name if f.parent != src else f.stem,
            "origin": "direct",
        })

    archives = sorted(
        f for f in src.iterdir()
        if f.is_file() and f.suffix.lower() in ARCHIVE_EXT
    )
    if archives:
        temp_root = Path(tempfile.mkdtemp(prefix="fish_photo_archives_"))
        for archive in archives:
            archives_scanned += 1
            try:
                extracted = extract_archive(archive, temp_root)
            except subprocess.CalledProcessError as exc:
                print(f"[WARN] archive extraction failed: {archive.name}: {exc.stderr.strip()}")
                continue
            images = [
                f for f in extracted.rglob("*")
                if f.is_file() and f.suffix.lower() in ALLOWED_EXT and not is_archive_cover_asset(f)
            ]
            for image in images:
                parent_name = image.parent.name if image.parent != extracted else archive.stem
                sources.append({
                    "path": image,
                    "context": archive.stem,
                    "container": parent_name,
                    "origin": "archive",
                    "archive": archive.name,
                })
    return sources, branding_assets, category_assets, archives_scanned, temp_root


def match_context_to_model_kods(context: str, model_kods: dict[str, dict]) -> list[str]:
    norm_context = normalize_text(context)
    compact_context = compact_text(context)
    ctx_tokens = token_set(context)
    if not norm_context:
        return []

    exact_like: list[str] = []
    fuzzy_candidates: list[tuple[int, str]] = []
    for pk, info in model_kods.items():
        display_name = info["display_name"]
        norm_model = normalize_text(display_name)
        compact_model = compact_text(display_name)
        model_tokens = token_set(display_name)

        if compact_context and compact_context in compact_model:
            exact_like.extend(info["kods"])
            continue
        if ctx_tokens and ctx_tokens.issubset(model_tokens):
            exact_like.extend(info["kods"])
            continue
        if HAS_FUZZ:
            score = fuzz.partial_ratio(norm_context, norm_model)
            if ctx_tokens:
                overlap = len(ctx_tokens & model_tokens)
                if overlap == 0:
                    continue
                score += min(overlap * 3, 12)
            fuzzy_candidates.append((score, pk))

    if exact_like:
        return sorted(set(exact_like))

    if not fuzzy_candidates:
        return []
    fuzzy_candidates.sort(reverse=True)
    best_score = fuzzy_candidates[0][0]
    if best_score < FUZZ_THRESHOLD:
        return []

    matched: list[str] = []
    for score, pk in fuzzy_candidates:
        if score < max(FUZZ_THRESHOLD, best_score - 6):
            break
        matched.extend(model_kods[pk]["kods"])
    return sorted(set(matched))


def match_variant_to_kods(
    hint: str,
    variant_index: dict[str, dict],
    candidate_kods: list[str] | None = None,
) -> list[str]:
    norm_hint = normalize_text(hint)
    compact_hint = compact_text(hint)
    hint_tokens = token_set(hint)
    if not norm_hint or not hint_tokens:
        return []

    candidate_set = set(candidate_kods or [])
    scores: list[tuple[int, str]] = []
    num_tokens = {t for t in hint_tokens if t.isdigit()}
    alpha_tokens = hint_tokens - num_tokens

    for kod, info in variant_index.items():
        if candidate_set and kod not in candidate_set:
            continue
        variant_tokens = info["tokens"]
        if not variant_tokens:
            continue

        overlap = hint_tokens & variant_tokens
        if not overlap:
            continue

        missing_alpha = alpha_tokens - variant_tokens
        missing_num = num_tokens - variant_tokens
        if alpha_tokens and len(missing_alpha) > max(1, len(alpha_tokens) // 2):
            continue
        if num_tokens and len(missing_num) == len(num_tokens):
            continue

        score = len(overlap) * 20
        score -= len(missing_alpha) * 16
        score -= len(missing_num) * 22
        if not missing_alpha:
            score += 35
        if num_tokens and not missing_num:
            score += 20
        if compact_hint and compact_hint in info["compact"]:
            score += 25
        if HAS_FUZZ:
            score += int(fuzz.token_set_ratio(norm_hint, info["norm"]) * 0.45)
            score += int(fuzz.partial_ratio(norm_hint, info["norm"]) * 0.25)

        scores.append((score, kod))

    if not scores:
        return []

    scores.sort(reverse=True)
    best_score = scores[0][0]
    min_score = 95 if len(hint_tokens) >= 3 else 85
    if best_score < min_score:
        return []

    matched = [kod for score, kod in scores if score >= max(min_score, best_score - 8)]
    return sorted(set(matched))


def match_file(
    filepath: Path,
    kod_to_parent: dict[str, str],
    model_kods: dict[str, dict],
    variant_index: dict[str, dict],
    overrides: dict[str, str],
    context_hint: str | None = None,
    container_hint: str | None = None,
) -> list[str]:
    """Повертає список kods, до яких належить фото."""
    name = filepath.stem
    family_kods = archive_override_kods(context_hint) or (
        match_context_to_model_kods(context_hint, model_kods) if context_hint else []
    )
    name_has_letters = has_letter(name)
    if not name_has_letters and family_kods and is_shared_archive(context_hint):
        return family_kods
    # 0. manual override
    if filepath.name in overrides:
        return [overrides[filepath.name]]
    if context_hint and context_hint in overrides:
        return [overrides[context_hint]]
    # 1a. цілий stem як kod (точний матч "302.jpg" → "302")
    if name in kod_to_parent:
        return [name]
    # 1a.bis: stem без trailing "_N" / "-N" суфіксу ("Y-5040-240_1" → "Y-5040-240")
    no_suffix = re.sub(r"[_\s](\d{1,3})$", "", name)
    if no_suffix != name and no_suffix in kod_to_parent:
        return [no_suffix]
    # 1b. артикули з крапками (1693.06.07)
    for m in KOD_DOTTED_RE.finditer(name):
        candidate = m.group(1)
        if candidate in kod_to_parent and (not name_has_letters or name.startswith(candidate)):
            return [candidate]
    # 1c. суфіксний trim (302_1, 302-front)
    stripped = re.split(r"[_\-\s]", name, maxsplit=1)[0]
    if stripped in kod_to_parent and (not name_has_letters or name.startswith(stripped)):
        return [stripped]
    # 1d. чисто цифровий artikul
    if not name_has_letters:
        for m in KOD_RE.finditer(name):
            candidate = m.group(1)
            if candidate in kod_to_parent:
                return [candidate]
    else:
        for m in KOD_RE.finditer(name):
            candidate = m.group(1)
            if candidate in kod_to_parent and m.start() == 0 and len(candidate) >= 4:
                return [candidate]

    base_name = strip_image_sequence(name)
    file_hint = base_name if has_letter(base_name) else ""
    if file_hint:
        matched = match_variant_to_kods(file_hint, variant_index, family_kods or None)
        if matched:
            return matched
        if container_hint and has_letter(container_hint):
            matched = match_variant_to_kods(
                f"{container_hint} {file_hint}",
                variant_index,
                family_kods or None,
            )
            if matched:
                return matched
        matched = match_variant_to_kods(file_hint, variant_index, None)
        if matched:
            return matched
        if container_hint and has_letter(container_hint):
            matched = match_variant_to_kods(
                f"{container_hint} {file_hint}",
                variant_index,
                None,
            )
            if matched:
                return matched
        if family_kods and is_shared_archive(context_hint):
            return family_kods
        return []

    if family_kods:
        return family_kods

    # 2. fuzzy match against model display_name → assign to all variants
    matched = match_context_to_model_kods(name, model_kods)
    if matched:
        return matched
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
    kod_to_parent, model_kods, variant_index = load_index(conn)
    overrides = load_overrides()

    if clear and not dry_run:
        if PUBLIC_PHOTOS.exists():
            shutil.rmtree(PUBLIC_PHOTOS)
        # Скинути pictures_json
        conn.execute("UPDATE variants SET pictures_json = '[]'")
        conn.commit()

    sources, branding_assets, category_assets, archives_scanned, temp_root = iter_image_sources(src)
    print(f"Scanning {len(sources)} image sources in {src}...")

    kod_to_urls: dict[str, list[str]] = {}
    seq_per_kod: dict[str, int] = {}
    matched = unmatched = 0
    unmatched_samples: list[str] = []
    archive_match_count = 0

    try:
        for item in sources:
            f = item["path"]
            kods = match_file(
                f,
                kod_to_parent,
                model_kods,
                variant_index,
                overrides,
                context_hint=item.get("context"),
                container_hint=item.get("container"),
            )
            if not kods:
                unmatched += 1
                if len(unmatched_samples) < 10:
                    sample = item.get("archive", f.name)
                    unmatched_samples.append(sample)
                continue
            results = copy_and_register(f, kods, seq_per_kod, dry_run)
            for kod, url in results:
                kod_to_urls.setdefault(kod, []).append(url)
            matched += 1
            if item.get("origin") == "archive":
                archive_match_count += 1

        written = 0
        if not dry_run and kod_to_urls:
            written = update_meta(conn, kod_to_urls)
    finally:
        conn.close()
        if temp_root and temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)

    summary = {
        "scanned": len(sources),
        "archives_scanned": archives_scanned,
        "archive_matched_files": archive_match_count,
        "matched_files": matched,
        "unmatched_files": unmatched,
        "kods_with_photos": len(kod_to_urls),
        "total_kods_in_db": len(kod_to_parent),
        "coverage_pct": round(100 * len(kod_to_urls) / max(len(kod_to_parent), 1), 1),
        "rows_updated": written,
        "branding_assets_detected": len(branding_assets),
        "category_assets_detected": len(category_assets),
        "branding_asset_samples": branding_assets[:5],
        "category_asset_samples": category_assets[:5],
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
