from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(r"D:\FISH\fish-sync")
META_DB = ROOT / "data" / "meta_store.sqlite"
LIVE_AUDIT = Path(r"D:\FISH\tmp\live_sitemap_image_audit.json")
OUTPUT_DIR = ROOT / "public" / "generated-product-images"
MAP_CACHE = ROOT / "data" / "live_missing_article_map.json"
REPORT_PATH = ROOT / "data" / "generated_product_image_report.json"

BASE_URL = "https://vsedliarybalky.com.ua"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "uk,en;q=0.9",
}

BG_TOP = "#0C1C2A"
BG_BOTTOM = "#102B43"
ACCENT = "#D97706"
TEXT_LIGHT = "#FFFFFF"
TEXT_DARK = "#1E293B"
MUTED = "#94A3B8"

SKU_PATTERNS = [
    re.compile(r'itemprop="sku"\s+content="([^"]+)"', re.I),
    re.compile(r'Артикул\s*</[^>]+>\s*([^<]+)', re.I),
    re.compile(r'property="product:sku"\s+content="([^"]+)"', re.I),
]
TITLE_PATTERN = re.compile(r"<title>(.*?)</title>", re.I | re.S)
H1_PATTERN = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")

FAMILY_LABELS = {
    "spinning": "Спінінг",
    "carp_rod": "Коропове вудилище",
    "bolognese_rod": "Болонське вудилище",
    "float_rod": "Махове вудилище",
    "feeder_rod": "Фідерне вудилище",
    "hook": "Гачки",
    "ready_rig": "Готові монтажі",
    "swivel": "Все для монтажу",
    "weight": "Грузила",
    "groundbait": "Прикормка",
    "pellets": "Пелетс",
    "pop_up": "Поп-ап",
    "pva_material": "PVA матеріали",
    "tool": "Рибальські інструменти",
    "line": "Волосінь та шнури",
    "fluorocarbon": "Флюорокарбон",
    "reel": "Котушка",
    "chair": "Крісла та стільці",
    "landing_net": "Підсаки",
    "keepnet": "Садки",
    "lure": "Приманки",
    "wobbler": "Воблер",
    "mandula": "Мандула",
    "float": "Поплавок",
    "tackle_box": "Органайзер",
    "bag": "Сумка",
    "cover": "Чохол",
    "winter_tackle": "Зимова ловля",
}

BRAND_HINTS = [
    ("Golden Catch", ("gc ", " gc", "golden catch")),
    ("Hayabusa", ("hayabusa",)),
    ("Owner", ("owner",)),
    ("Kaida", ("kaida",)),
    ("Kamatsu", ("kamatsu", "kamalsu")),
    ("Korda", ("korda",)),
    ("Cobra", ("cobra",)),
    ("Feima", ("feima", "afeima")),
    ("Winner", ("winner", "winer")),
]


@dataclass
class VariantInfo:
    article: str
    name: str
    brand: str
    family: str
    source_category: str
    display_name: str
    length_m: float | None
    test_min: float | None
    test_max: float | None
    action: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--force-remap", action="store_true")
    parser.add_argument("--clear", action="store_true")
    return parser.parse_args()


def load_missing_urls() -> list[str]:
    payload = json.loads(LIVE_AUDIT.read_text(encoding="utf-8"))
    return [str(url).strip() for url in payload.get("missing_urls", []) if str(url).strip()]


def fetch_challenge_hash() -> str:
    response = requests.get(BASE_URL, headers=HEADERS, timeout=60)
    match = re.search(r'const defaultHash = "([^"]+)"', response.text)
    if not match:
        raise RuntimeError("Could not extract anti-bot challenge hash from storefront")
    return match.group(1)


def clean_html_text(value: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", value or "")).strip()


def infer_brand(existing_brand: str, name: str) -> str:
    brand = (existing_brand or "").strip()
    if brand:
        return brand
    lowered = f" {name.casefold()} "
    for label, hints in BRAND_HINTS:
        if any(hint in lowered for hint in hints):
            return label
    return ""


def extract_article_and_title(html_text: str) -> tuple[str | None, str | None]:
    article = None
    for pattern in SKU_PATTERNS:
        match = pattern.search(html_text)
        if match:
            article = match.group(1).strip()
            break
    title = None
    h1_match = H1_PATTERN.search(html_text)
    if h1_match:
        title = clean_html_text(h1_match.group(1))
    if not title:
        title_match = TITLE_PATTERN.search(html_text)
        if title_match:
            title = clean_html_text(title_match.group(1))
    return article, title


def fetch_article_mapping(url: str, challenge_hash: str) -> dict:
    session = requests.Session()
    session.headers.update(HEADERS)
    session.cookies.set("challenge_passed", challenge_hash, domain="vsedliarybalky.com.ua", path="/")
    response = session.get(url, timeout=60)
    response.raise_for_status()
    article, title = extract_article_and_title(response.text)
    return {
        "url": url,
        "article": article,
        "title": title,
        "ok": bool(article),
    }


def load_or_build_article_map(
    urls: list[str],
    concurrency: int,
    force_remap: bool,
) -> list[dict]:
    if MAP_CACHE.exists() and not force_remap:
        payload = json.loads(MAP_CACHE.read_text(encoding="utf-8"))
        cached = payload.get("items", [])
        if len(cached) == len(urls):
            return cached

    challenge_hash = fetch_challenge_hash()
    items: list[dict] = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_map = {executor.submit(fetch_article_mapping, url, challenge_hash): url for url in urls}
        for future in as_completed(future_map):
            url = future_map[future]
            try:
                items.append(future.result())
            except Exception as exc:  # noqa: BLE001
                items.append({"url": url, "article": None, "title": None, "ok": False, "error": str(exc)})

    items.sort(key=lambda item: item["url"])
    payload = {"count": len(items), "items": items}
    MAP_CACHE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return items


def load_variants() -> dict[str, VariantInfo]:
    conn = sqlite3.connect(META_DB)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
              v.kod,
              v.name_raw,
              v.length_m,
              v.test_min,
              v.test_max,
              v.action,
              m.brand,
              m.family,
              m.source_category,
              m.display_name
            FROM variants v
            JOIN models m ON m.parent_key = v.parent_key
            """
        ).fetchall()
    finally:
        conn.close()

    data: dict[str, VariantInfo] = {}
    for row in rows:
        article = str(row["kod"]).strip()
        data[article] = VariantInfo(
            article=article,
            name=str(row["name_raw"] or row["display_name"] or article).strip(),
            brand=infer_brand(str(row["brand"] or "").strip(), str(row["name_raw"] or row["display_name"] or article).strip()),
            family=str(row["family"] or "").strip(),
            source_category=str(row["source_category"] or "").strip(),
            display_name=str(row["display_name"] or "").strip(),
            length_m=row["length_m"],
            test_min=row["test_min"],
            test_max=row["test_max"],
            action=str(row["action"] or "").strip(),
        )
    return data


def ensure_output_dir(clear: bool) -> None:
    if clear and OUTPUT_DIR.exists():
        for child in OUTPUT_DIR.iterdir():
            if child.is_dir():
                for nested in child.rglob("*"):
                    if nested.is_file():
                        nested.unlink()
                for nested in sorted(child.rglob("*"), reverse=True):
                    if nested.is_dir():
                        nested.rmdir()
                child.rmdir()
            else:
                child.unlink()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def wrap_text(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if len(test) <= width:
            current = test
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines


def make_gradient(width: int, height: int) -> Image.Image:
    top = Image.new("RGB", (width, height), BG_TOP)
    bottom = Image.new("RGB", (width, height), BG_BOTTOM)
    mask = Image.new("L", (width, height))
    for y in range(height):
        mask.putpixel((0, y), min(255, int(255 * (y / max(1, height - 1)))))
    mask = mask.resize((width, height))
    return Image.composite(bottom, top, mask)


def draw_background(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    draw.rounded_rectangle((60, 60, width - 60, height - 60), radius=48, outline=(255, 255, 255, 18), width=2)
    draw.polygon([(width - 280, 0), (width, 0), (width, 280)], fill=ACCENT)
    draw.rectangle((0, height - 120, width, height), fill=(255, 255, 255, 10))
    for idx in range(5):
        y = 180 + idx * 180
        draw.arc((-200, y, width + 200, y + 240), start=0, end=180, fill=(255, 255, 255, 18), width=2)


def draw_icon(draw: ImageDraw.ImageDraw, family: str, width: int, height: int) -> None:
    cx = width - 250
    cy = 340
    icon_color = (255, 255, 255, 80)
    accent = (217, 119, 6, 180)
    family = (family or "").lower()

    if "reel" in family:
        draw.ellipse((cx - 80, cy - 80, cx + 80, cy + 80), outline=icon_color, width=8)
        draw.ellipse((cx - 30, cy - 30, cx + 30, cy + 30), outline=accent, width=8)
        draw.line((cx + 78, cy, cx + 130, cy - 50), fill=icon_color, width=8)
        draw.line((cx + 120, cy - 40, cx + 170, cy - 15), fill=accent, width=8)
        return

    if "hook" in family:
        draw.arc((cx - 90, cy - 100, cx + 70, cy + 60), start=220, end=40, fill=icon_color, width=10)
        draw.line((cx + 5, cy - 135, cx + 5, cy - 30), fill=accent, width=10)
        draw.line((cx - 20, cy + 20, cx + 35, cy + 65), fill=icon_color, width=8)
        return

    if "pellets" in family or "groundbait" in family or "pop" in family:
        for dx in (-70, 0, 70):
            draw.ellipse((cx + dx - 38, cy - 38, cx + dx + 38, cy + 38), fill=(255, 255, 255, 36), outline=accent, width=4)
        return

    if "chair" in family:
        draw.line((cx - 80, cy - 20, cx + 80, cy - 20), fill=icon_color, width=10)
        draw.line((cx - 60, cy - 70, cx + 40, cy - 70), fill=accent, width=10)
        draw.line((cx - 60, cy - 70, cx - 80, cy - 20), fill=icon_color, width=8)
        draw.line((cx + 40, cy - 70, cx + 80, cy - 20), fill=icon_color, width=8)
        draw.line((cx - 60, cy - 20, cx - 90, cy + 80), fill=icon_color, width=8)
        draw.line((cx + 60, cy - 20, cx + 90, cy + 80), fill=icon_color, width=8)
        return

    if "line" in family or "fluoro" in family:
        draw.ellipse((cx - 85, cy - 85, cx + 85, cy + 85), outline=icon_color, width=8)
        draw.arc((cx - 45, cy - 45, cx + 45, cy + 45), start=0, end=320, fill=accent, width=8)
        return

    # Default rod silhouette
    draw.line((cx - 140, cy + 80, cx + 150, cy - 110), fill=icon_color, width=8)
    for idx in range(4):
        draw.ellipse((cx - 40 + idx * 45, cy - 10 - idx * 22, cx - 20 + idx * 45, cy + 10 - idx * 22), outline=accent, width=4)


def spec_lines(info: VariantInfo) -> list[str]:
    specs: list[str] = []
    family_label = FAMILY_LABELS.get(info.family, info.source_category.split("/")[-1].strip() if info.source_category else "")
    if family_label:
        specs.append(family_label)
    if info.length_m:
        specs.append(f"Довжина: {info.length_m:g} м")
    if info.test_min is not None and info.test_max is not None:
        specs.append(f"Тест: {info.test_min:g}-{info.test_max:g} г")
    if info.action:
        specs.append(f"Лад: {info.action}")
    specs.append(f"Артикул: {info.article}")
    return specs[:4]


def build_placeholder(info: VariantInfo, output_path: Path) -> None:
    width = 1400
    height = 1400
    image = make_gradient(width, height)
    image = image.filter(ImageFilter.GaussianBlur(radius=0.2))
    draw = ImageDraw.Draw(image, "RGBA")
    draw_background(draw, width, height)
    draw_icon(draw, info.family, width, height)

    brand_font = load_font(42, bold=True)
    title_font = load_font(74, bold=True)
    body_font = load_font(38, bold=False)
    meta_font = load_font(28, bold=False)

    brand = info.brand or "Все для рибалки"
    brand_box = (90, 90, 90 + 420, 160)
    draw.rounded_rectangle(brand_box, radius=24, fill=(255, 255, 255, 28), outline=(255, 255, 255, 32), width=2)
    draw.text((120, 108), brand.upper(), font=brand_font, fill=TEXT_LIGHT)

    family_label = FAMILY_LABELS.get(info.family, "")
    if family_label:
        draw.rounded_rectangle((90, 195, 90 + 320, 250), radius=18, fill=(217, 119, 6, 210))
        draw.text((116, 207), family_label, font=meta_font, fill=TEXT_LIGHT)

    title_lines = wrap_text(info.name, width=24)[:5]
    y = 320
    for line in title_lines:
        draw.text((100, y), line, font=title_font, fill=TEXT_LIGHT)
        y += 96

    y += 20
    for line in spec_lines(info):
        draw.text((102, y), line, font=body_font, fill=(255, 255, 255, 220))
        y += 60

    badge_text = "Оригінальна ілюстрація"
    badge_w = int(draw.textlength(badge_text, font=meta_font)) + 42
    draw.rounded_rectangle((100, height - 190, 100 + badge_w, height - 132), radius=18, fill=(255, 255, 255, 24))
    draw.text((122, height - 177), badge_text, font=meta_font, fill=MUTED)

    footer = "Фото-відповідник тимчасово відсутній. Зображення оновиться після отримання оригіналу."
    footer_lines = textwrap.wrap(footer, width=74)
    fy = height - 120
    for line in footer_lines:
        draw.text((100, fy), line, font=meta_font, fill=(255, 255, 255, 180))
        fy += 34

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="JPEG", quality=90, optimize=True)


def iter_target_articles(items: Iterable[dict], variants: dict[str, VariantInfo]) -> list[VariantInfo]:
    out: list[VariantInfo] = []
    seen: set[str] = set()
    for item in items:
        article = str(item.get("article") or "").strip()
        if not article or article in seen:
            continue
        if article not in variants:
            continue
        seen.add(article)
        out.append(variants[article])
    return out


def main() -> int:
    args = parse_args()
    urls = load_missing_urls()
    if args.limit:
        urls = urls[: args.limit]
    ensure_output_dir(args.clear)

    article_map = load_or_build_article_map(urls, concurrency=args.concurrency, force_remap=args.force_remap)
    variants = load_variants()
    targets = iter_target_articles(article_map, variants)

    generated: list[dict] = []
    missing_in_db: list[dict] = []
    for item in article_map:
        article = str(item.get("article") or "").strip()
        if article and article not in variants:
            missing_in_db.append(item)

    for info in targets:
        article_dir = OUTPUT_DIR / info.article
        image_path = article_dir / "1.jpg"
        build_placeholder(info, image_path)
        generated.append(
            {
                "article": info.article,
                "path": str(image_path),
                "name": info.name,
                "brand": info.brand,
                "family": info.family,
            }
        )

    ok_count = sum(1 for item in article_map if item.get("ok"))
    payload = {
        "live_urls_total": len(urls),
        "mapped_ok": ok_count,
        "mapped_failed": len(article_map) - ok_count,
        "generated_count": len(generated),
        "missing_in_db_count": len(missing_in_db),
        "generated_sample": generated[:20],
        "missing_in_db_sample": missing_in_db[:20],
        "output_dir": str(OUTPUT_DIR),
        "map_cache": str(MAP_CACHE),
    }
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
