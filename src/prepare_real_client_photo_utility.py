from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from photo_sync import (
    META_DB,
    ROOT,
    is_archive_cover_asset,
    load_index,
    load_overrides,
    match_file,
    normalize_text,
    iter_image_sources,
)


DEFAULT_SOURCE_ROOT = Path(r"F:\FISH_IMAGES\_extracted")
DEFAULT_OUTPUT_ROOT = ROOT / "public" / "real-client-photo-utility"
DEFAULT_REPORT = ROOT / "data" / "real_client_photo_utility_report.json"
DEFAULT_VALID_ARTICLES_XML = ROOT / "public" / "horoshop.xml"
WINDOWS_FORBIDDEN = re.compile(r'[<>:"/\\|?*]')
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
SKIP_DIRS = {"_contact_sheets", "__macosx"}
TECHNICAL_NAME_HINTS = {
    "image 2026",
    "screenshot",
    "скрін",
    "скрин",
    "таблиц",
    "excel",
}


@dataclass
class PreparedPhoto:
    article: str
    source: str
    target: str
    context: str
    container: str
    source_width: int
    source_height: int
    bytes: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--max-per-article", type=int, default=5)
    parser.add_argument("--max-side", type=int, default=1800)
    parser.add_argument("--quality", type=int, default=88)
    parser.add_argument("--min-side", type=int, default=240)
    parser.add_argument("--min-bytes", type=int, default=15_000)
    parser.add_argument("--exclude-articles", nargs="*", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--clear", action="store_true")
    return parser.parse_args()


def is_safe_article(article: str) -> bool:
    return bool(article.strip(". ")) and not WINDOWS_FORBIDDEN.search(article)


def gallery_filename(article: str, index: int) -> str:
    if index == 1:
        return f"{article}@gallery_common.jpg"
    return f"{article}@gallery_common@{index}.jpg"


def safe_clear_output_root(output_root: Path) -> None:
    resolved = output_root.resolve()
    public_root = (ROOT / "public").resolve()
    if public_root not in resolved.parents:
        raise RuntimeError(f"Refusing to clear outside project public directory: {resolved}")
    if resolved.name not in {"real-client-photo-utility", "real-photo-utility"}:
        raise RuntimeError(f"Refusing to clear unexpected output directory: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def load_valid_articles(xml_path: Path) -> set[str]:
    if not xml_path.exists():
        return set()
    import xml.etree.ElementTree as ET

    root = ET.parse(xml_path).getroot()
    return {
        str(offer.attrib.get("id") or "").strip()
        for offer in root.findall(".//offer")
        if str(offer.attrib.get("id") or "").strip()
    }


def is_technical_image(path: Path, source_root: Path) -> bool:
    rel_parts = {part.casefold() for part in path.relative_to(source_root).parts[:-1]}
    if rel_parts & SKIP_DIRS:
        return True
    norm_name = normalize_text(path.stem)
    return any(hint in norm_name for hint in TECHNICAL_NAME_HINTS)


def image_info(path: Path) -> tuple[int, int] | None:
    try:
        with Image.open(path) as image:
            return image.size
    except (UnidentifiedImageError, OSError):
        return None


def should_skip_by_quality(path: Path, source_root: Path, min_side: int, min_bytes: int) -> str | None:
    if path.suffix.lower() not in ALLOWED_EXT:
        return "unsupported_extension"
    if is_archive_cover_asset(path):
        return "archive_cover_asset"
    if is_technical_image(path, source_root):
        return "technical_or_contact_sheet"
    try:
        size = path.stat().st_size
    except OSError:
        return "stat_failed"
    if size < min_bytes:
        return "too_small_file"
    dims = image_info(path)
    if not dims:
        return "invalid_image"
    width, height = dims
    if min(width, height) < min_side:
        return "too_small_dimensions"
    return None


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def convert_to_jpeg(source: Path, target: Path, max_side: int, quality: int) -> tuple[int, int, int]:
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image)
        if image.mode not in {"RGB", "L"}:
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode in {"RGBA", "LA"}:
                background.paste(image.convert("RGBA"), mask=image.convert("RGBA").split()[-1])
                image = background
            else:
                image = image.convert("RGB")
        else:
            image = image.convert("RGB")
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, "JPEG", quality=quality, optimize=True, progressive=True)
        width, height = image.size
    return width, height, target.stat().st_size


def sort_source_key(item: dict) -> tuple[str, str, str]:
    path = Path(item["path"])
    return (
        normalize_text(str(item.get("context") or "")),
        normalize_text(str(item.get("container") or "")),
        normalize_text(path.name),
    )


_GALLERY_ORDER_RE = re.compile(r"^(\d+)(?:[.,](\d+))?")


def gallery_order_key(item: dict) -> tuple[int, int]:
    """Головне фото ("11.jpg") завжди перед додатковими ракурсами
    ("11,1.jpg", "11,2.jpg") — інакше рядковий сорт файлів ставить
    ракурси-макро перед головним кадром (цифра '1' < літера 'j' в 'jpg')."""
    name = Path(item["path"]).stem
    m = _GALLERY_ORDER_RE.match(name)
    if not m:
        return (0, 0)
    base = int(m.group(1))
    sub = int(m.group(2)) if m.group(2) else 0
    return (base, sub)


def build_utility(args: argparse.Namespace) -> dict:
    source_root = args.src.resolve()
    if not source_root.exists():
        raise FileNotFoundError(f"Source root not found: {source_root}")

    conn = sqlite3.connect(META_DB)
    try:
        kod_to_parent, model_kods, variant_index = load_index(conn)
    finally:
        conn.close()
    overrides = load_overrides()
    valid_articles = load_valid_articles(DEFAULT_VALID_ARTICLES_XML)
    excluded_articles = {str(article).strip() for article in args.exclude_articles if str(article).strip()}

    sources, branding_assets, category_assets, archives_scanned, temp_root = iter_image_sources(source_root)
    selected_by_article: dict[str, list[dict]] = defaultdict(list)
    skipped: list[dict] = []
    unmatched: list[dict] = []
    excluded_matched_files: list[dict] = []
    unsafe_articles: list[dict] = []
    duplicate_sources = 0
    seen_article_hashes: set[tuple[str, str]] = set()

    try:
        for item in sorted(sources, key=sort_source_key):
            path = Path(item["path"])
            skip_reason = should_skip_by_quality(path, source_root, args.min_side, args.min_bytes)
            if skip_reason:
                skipped.append({"path": str(path), "reason": skip_reason})
                continue

            matched_kods = match_file(
                path,
                kod_to_parent,
                model_kods,
                variant_index,
                overrides,
                context_hint=item.get("context"),
                container_hint=item.get("container"),
            )
            excluded_kods = [kod for kod in matched_kods if kod in excluded_articles]
            kods = [
                kod for kod in matched_kods
                if kod in kod_to_parent
                and kod not in excluded_articles
                and (not valid_articles or kod in valid_articles)
            ]
            if not kods:
                if excluded_kods:
                    excluded_matched_files.append(
                        {
                            "path": str(path),
                            "excluded_articles": sorted(set(excluded_kods)),
                            "context": str(item.get("context") or ""),
                            "container": str(item.get("container") or ""),
                        }
                    )
                    continue
                unmatched.append(
                    {
                        "path": str(path),
                        "context": str(item.get("context") or ""),
                        "container": str(item.get("container") or ""),
                    }
                )
                continue

            source_hash = file_hash(path)
            for kod in kods:
                if not is_safe_article(kod):
                    unsafe_articles.append({"article": kod, "path": str(path)})
                    continue
                if len(selected_by_article[kod]) >= args.max_per_article:
                    continue
                key = (kod, source_hash)
                if key in seen_article_hashes:
                    duplicate_sources += 1
                    continue
                seen_article_hashes.add(key)
                width, height = image_info(path) or (0, 0)
                selected_by_article[kod].append(
                    {
                        "path": path,
                        "context": str(item.get("context") or ""),
                        "container": str(item.get("container") or ""),
                        "width": width,
                        "height": height,
                    }
                )
    finally:
        if temp_root and temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)

    prepared: list[PreparedPhoto] = []
    output_root = args.output_root.resolve()
    if not args.dry_run:
        if args.clear:
            safe_clear_output_root(output_root)
        else:
            output_root.mkdir(parents=True, exist_ok=True)

    for article, items in sorted(selected_by_article.items(), key=lambda pair: pair[0].casefold()):
        items = sorted(items, key=gallery_order_key)
        for index, item in enumerate(items, start=1):
            target = output_root / gallery_filename(article, index)
            if args.dry_run:
                bytes_written = 0
            else:
                _, _, bytes_written = convert_to_jpeg(
                    Path(item["path"]),
                    target,
                    max_side=args.max_side,
                    quality=args.quality,
                )
            prepared.append(
                PreparedPhoto(
                    article=article,
                    source=str(item["path"]),
                    target=str(target),
                    context=item["context"],
                    container=item["container"],
                    source_width=int(item["width"]),
                    source_height=int(item["height"]),
                    bytes=bytes_written,
                )
            )

    per_article_counts = {
        article: len(items)
        for article, items in sorted(selected_by_article.items(), key=lambda pair: pair[0].casefold())
    }
    report = {
        "status": "dry_run" if args.dry_run else "complete",
        "source_root": str(source_root),
        "output_root": str(output_root),
        "scanned_sources": len(sources),
        "archives_scanned": archives_scanned,
        "branding_assets_detected": len(branding_assets),
        "category_assets_detected": len(category_assets),
        "quality_skipped_count": len(skipped),
        "unmatched_source_files": len(unmatched),
        "excluded_matched_files": len(excluded_matched_files),
        "unsafe_article_files": len(unsafe_articles),
        "duplicate_source_assignments_skipped": duplicate_sources,
        "matched_articles": len(selected_by_article),
        "prepared_photo_files": len(prepared),
        "max_per_article": args.max_per_article,
        "excluded_articles": sorted(excluded_articles),
        "policy": (
            "Only local client-supplied photos from F:\\FISH_IMAGES are prepared here. "
            "Internet-sourced product photos are intentionally not used; products without a client photo should keep generated placeholders."
        ),
        "per_article_counts": per_article_counts,
        "prepared_sample": [asdict(item) for item in prepared[:40]],
        "unmatched_samples": unmatched[:40],
        "excluded_matched_samples": excluded_matched_files[:40],
        "skipped_samples": skipped[:40],
        "unsafe_article_samples": unsafe_articles[:40],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    args = parse_args()
    report = build_utility(args)
    print(
        json.dumps(
            {
                "status": report["status"],
                "source_root": report["source_root"],
                "output_root": report["output_root"],
                "scanned_sources": report["scanned_sources"],
                "matched_articles": report["matched_articles"],
                "prepared_photo_files": report["prepared_photo_files"],
                "unmatched_source_files": report["unmatched_source_files"],
                "quality_skipped_count": report["quality_skipped_count"],
                "report": str(args.report),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
