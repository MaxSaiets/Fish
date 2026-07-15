from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from pathlib import Path

import requests
import urllib3
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from upload_horoshop_category_visuals import SLUG_FAMILY_RULES, family_for_slug


urllib3.disable_warnings()

ROOT = Path(r"D:\FISH\fish-sync")
ENV_FILE = ROOT / ".env"
REPORT = ROOT / "data" / "horoshop_category_visuals_report.json"
OUT_DIR = ROOT / "public" / "site-category-assets-unique-all"
INVENTORY = Path(r"F:\FISH_IMAGES\_extracted\_image_inventory.csv")
EXTRACTED_ROOT = Path(r"F:\FISH_IMAGES\_extracted")

FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")
FONT_REGULAR = Path(r"C:\Windows\Fonts\arial.ttf")

FAMILY_FALLBACK = {
    "rod": "rod",
    "reel": "reel",
    "line": "line",
    "hook": "hook",
    "lure": "lure",
    "winter": "winter",
    "camp": "camp",
    "water": "water",
}

SLUG_KEYWORDS = {
    "hach": {"гач", "hook", "offset", "офсет", "двійник", "трійник"},
    "kormush": {"годівниц", "кормуш", "feeder", "method"},
    "hruzyla": {"груз", "lead", "weight"},
    "montazh": {"монтаж", "rig", "оснаст", "повід"},
    "prykorm": {"прикорм", "groundbait", "fanatik", "anvi", "real", "fish"},
    "pelets": {"пелет", "pellet", "pelets"},
    "boil": {"бойл", "boil"},
    "pop": {"pop", "поп"},
    "pva": {"pva", "пва"},
    "vudylysh": {"вуд", "rod", "удилище", "apex", "titan", "weida", "mifine"},
}


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_FILE.exists():
        for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def normalize(text: str) -> str:
    text = text.lower()
    table = str.maketrans(
        {
            "а": "a",
            "б": "b",
            "в": "v",
            "г": "h",
            "ґ": "g",
            "д": "d",
            "е": "e",
            "є": "ie",
            "ж": "zh",
            "з": "z",
            "и": "y",
            "і": "i",
            "ї": "i",
            "й": "i",
            "к": "k",
            "л": "l",
            "м": "m",
            "н": "n",
            "о": "o",
            "п": "p",
            "р": "r",
            "с": "s",
            "т": "t",
            "у": "u",
            "ф": "f",
            "х": "kh",
            "ц": "ts",
            "ч": "ch",
            "ш": "sh",
            "щ": "shch",
            "ь": "",
            "ю": "iu",
            "я": "ia",
        }
    )
    return re.sub(r"[^a-z0-9]+", " ", text.translate(table)).strip()


def token_set(text: str) -> set[str]:
    return {part for part in normalize(text).split() if len(part) >= 3}


def load_inventory() -> list[dict[str, str]]:
    if not INVENTORY.exists():
        return []
    rows: list[dict[str, str]] = []
    with INVENTORY.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("is_image") == "True" and not row.get("issues"):
                path = EXTRACTED_ROOT / row["relative_path"]
                if path.exists():
                    row["abs_path"] = str(path)
                    row["tokens"] = " ".join([row.get("archive", ""), row.get("relative_path", ""), row.get("file_name", "")])
                    rows.append(row)
    return rows


def fetch_slug_titles(base_url: str) -> dict[str, str]:
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (compatible; fish-sync-category-title-map/1.0)"
    response = session.get(base_url, timeout=60)
    match = re.search(r'defaultHash\s*=\s*"([^"]+)"', response.text)
    if match:
        session.cookies.set("challenge_passed", match.group(1), domain="vsedliarybalky.com.ua", path="/")
        response = session.get(base_url, timeout=60)
    titles: dict[str, str] = {}
    for match in re.finditer(r'<a[^>]+href="(/[a-z0-9\-]+/)"[^>]*>(.*?)</a>', response.text, re.S):
        slug = match.group(1)
        text = re.sub(r"<[^>]+>", " ", match.group(2))
        text = re.sub(r"\s+", " ", text).strip()
        if not text or text == "Всі категорії":
            continue
        titles.setdefault(slug, text)
    return titles


def title_from_slug(slug: str, titles: dict[str, str]) -> str:
    if slug in titles:
        return titles[slug]
    return " ".join(part.capitalize() for part in slug.strip("/").replace("-", " ").split())


def wanted_tokens(slug: str, title: str) -> set[str]:
    wanted = token_set(slug + " " + title)
    for key, values in SLUG_KEYWORDS.items():
        if key in normalize(slug):
            wanted |= token_set(" ".join(values))
    family = family_for_slug(slug)
    for pattern, pattern_family in SLUG_FAMILY_RULES:
        if pattern_family == family and re.search(pattern, slug.strip("/")):
            wanted |= token_set(pattern.replace("|", " "))
    return wanted


def image_score(row: dict[str, str], wanted: set[str]) -> float:
    row_tokens = token_set(row.get("tokens", ""))
    name_tokens = token_set(row.get("file_name", ""))
    archive_tokens = token_set(row.get("archive", ""))
    return (
        len(wanted & row_tokens)
        + len(wanted & name_tokens) * 1.8
        + len(wanted & archive_tokens) * 1.2
        + min(float(row.get("megapixels") or 0), 2.0) * 0.15
    )


def choose_source(slug: str, title: str, inventory: list[dict[str, str]], used_hashes: set[str], report: dict) -> tuple[str, Path, str]:
    unique_prepared = ((report.get("unique_archive_previews") or {}).get("prepared") or {})
    for item in unique_prepared.values():
        if item.get("slug") == slug and item.get("local_path") and Path(item["local_path"]).exists():
            return "archive-exact", Path(item["local_path"]), str(item.get("source", ""))

    wanted = wanted_tokens(slug, title)
    best: tuple[float, dict[str, str] | None] = (-1, None)
    for row in inventory:
        penalty = 2.5 if row.get("sha256") in used_hashes else 0
        score = image_score(row, wanted) - penalty
        if score > best[0]:
            best = (score, row)
    if best[1] and best[0] >= 1.4:
        used_hashes.add(best[1].get("sha256", ""))
        return "archive-match", Path(best[1]["abs_path"]), best[1].get("relative_path", "")

    family = FAMILY_FALLBACK.get(family_for_slug(slug), "water")
    prepared = report.get("prepared") or {}
    local_path = prepared.get(family, {}).get("local_path") if isinstance(prepared.get(family), dict) else ""
    if local_path and Path(local_path).exists():
        return f"open-stock-{family}", Path(local_path), str(prepared.get(family, {}).get("source_page", ""))

    return "missing", Path(), ""


def load_font(path: Path, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:
        return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:3]


def render_preview(source: Path, target: Path, title: str, slug: str, source_type: str) -> None:
    digest = hashlib.sha256(slug.encode("utf-8")).digest()
    image = Image.open(source).convert("RGB")
    center = (0.38 + digest[0] / 255 * 0.24, 0.38 + digest[1] / 255 * 0.24)
    image = ImageOps.fit(image, (1200, 840), method=Image.Resampling.LANCZOS, centering=center)
    image = ImageEnhance.Color(image).enhance(1.04 + digest[2] / 255 * 0.08)
    image = ImageEnhance.Contrast(image).enhance(1.05 + digest[3] / 255 * 0.08)

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    accent = (217, 119, 6, 230)
    draw.rectangle((0, 0, 1200, 840), fill=(12, 28, 42, 20 + digest[4] % 35))
    draw.rectangle((0, 548, 1200, 840), fill=(12, 28, 42, 180))
    draw.rounded_rectangle((34, 34, 250, 86), radius=17, fill=accent)

    font_brand = load_font(FONT_BOLD, 28)
    font_title = load_font(FONT_BOLD, 58)
    font_small = load_font(FONT_REGULAR, 25)
    draw.text((54, 47), "ВСЕ ДЛЯ РИБАЛКИ", fill=(255, 255, 255, 255), font=font_brand)
    lines = wrap_text(draw, title, font_title, 1030)
    y = 590
    for line in lines:
        draw.text((54, y), line, fill=(255, 255, 255, 255), font=font_title)
        y += 66
    draw.text((56, 786), "Категорія магазину", fill=(222, 231, 239, 225), font=font_small)
    draw.text((950, 786), source_type.replace("-", " "), fill=(222, 231, 239, 145), font=font_small)
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "JPEG", quality=86, optimize=True, progressive=True)


def admin_login(session: requests.Session, base_url: str, login: str, password: str) -> None:
    response = session.post(
        f"{base_url}/core-api/admin/security/login",
        json={"login": login, "password": password},
        timeout=90,
        verify=False,
    )
    response.raise_for_status()
    data = response.json()
    if int(data.get("status") or 0) != 200:
        raise RuntimeError(f"Horoshop auth failed: {data}")


def upload_asset(session: requests.Session, base_url: str, path: Path) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, 5):
        try:
            with path.open("rb") as fh:
                response = session.post(
                    f"{base_url}/core-api/admin/app-json/upload-image",
                    files={"file": (path.name, fh)},
                    timeout=180,
                    verify=False,
                )
            response.raise_for_status()
            data = response.json()
            payload = data.get("payload") if isinstance(data, dict) else None
            if not payload:
                raise RuntimeError(f"Unexpected upload response for {path.name}: {data}")
            item = payload[0] if isinstance(payload, list) else payload
            uri = str(item.get("uri") or item.get("url") or "").strip()
            if uri.startswith("/content/"):
                uri = uri.replace("/content/", "/", 1)
            if uri.startswith("/"):
                uri = f"{base_url}{uri}"
            return {"local_path": str(path), "uri": uri, "response": item}
        except Exception as exc:
            last_error = exc
            time.sleep(2 * attempt)
    raise RuntimeError(f"Upload failed after retries for {path}: {last_error}")


def key_for_slug(slug: str) -> str:
    return "cat_unique_" + re.sub(r"[^a-z0-9]+", "_", slug.strip("/")).strip("_")


def main() -> int:
    env = load_env()
    base_url = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    slugs = sorted((report.get("category_map") or {}).keys())
    titles = fetch_slug_titles(base_url)
    inventory = load_inventory()
    used_hashes: set[str] = set()

    def new_session() -> requests.Session:
        fresh = requests.Session()
        fresh.headers["User-Agent"] = "fish-sync-all-unique-category-previews/1.0"
        admin_login(fresh, base_url, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])
        return fresh

    session = new_session()

    uploads = report.setdefault("uploads", {})
    category_map = dict(report.get("category_map") or {})
    prepared: dict[str, dict[str, str]] = {}
    source_counts: dict[str, int] = {}
    existing_partial = report.get("all_unique_previews_partial") or {}

    for slug in slugs:
        title = title_from_slug(slug, titles)
        key = key_for_slug(slug)
        existing = uploads.get(key)
        if isinstance(existing, dict) and str(existing.get("uri") or "").startswith("http"):
            category_map[slug] = key
            existing_item = existing_partial.get(key)
            if isinstance(existing_item, dict):
                prepared[key] = existing_item
                source_type = str(existing_item.get("source_type") or "existing")
                source_counts[source_type] = source_counts.get(source_type, 0) + 1
            continue
        source_type, source_path, source_note = choose_source(slug, title, inventory, used_hashes, report)
        if not source_path.exists():
            continue
        target = OUT_DIR / f"{key}.jpg"
        render_preview(source_path, target, title, slug, source_type)
        try:
            uploads[key] = upload_asset(session, base_url, target)
        except Exception:
            session = new_session()
            uploads[key] = upload_asset(session, base_url, target)
        category_map[slug] = key
        prepared[key] = {
            "slug": slug,
            "title": title,
            "source_type": source_type,
            "source": str(source_path),
            "source_note": source_note,
            "local_path": str(target),
            "uri": uploads[key]["uri"],
        }
        source_counts[source_type] = source_counts.get(source_type, 0) + 1
        report["category_map"] = category_map
        report.setdefault("all_unique_previews_partial", {})[key] = prepared[key]
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(0.25)

    report["category_map"] = category_map
    report["all_unique_previews"] = {
        "count": len(prepared),
        "expected": len(slugs),
        "source_counts": source_counts,
        "prepared": prepared,
        "not_prepared": sorted(set(slugs) - {item["slug"] for item in prepared.values()}),
        "policy": "Unique category preview images generated from user-provided archive images where possible, otherwise from documented open-stock assets already stored in the report. No competitor scraping or watermark removal.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["all_unique_previews"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
