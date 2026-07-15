from __future__ import annotations

import argparse
import json
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable

import requests


ROOT = Path(r"D:\FISH\fish-sync")
OUT_REPORT = ROOT / "data" / "live_product_media_audit.json"
LIVE_MAP_CACHE = ROOT / "data" / "live_missing_article_map.json"
SPECIAL_UPLOAD_REPORT = ROOT / "data" / "horoshop_special_placeholder_upload_report.json"
GENERATED_IMAGES_ROOT = ROOT / "public" / "generated-product-images"
BASE_URL = "https://vsedliarybalky.com.ua"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "uk,en;q=0.9",
}

IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.I)
CLASS_ATTR_RE = re.compile(r"""\bclass\s*=\s*["']([^"']*)["']""", re.I)
SRC_ATTR_RE = re.compile(r"""\bsrc\s*=\s*["']([^"']+)["']""", re.I)
NO_PHOTO_GALLERY_RE = re.compile(
    r"""<(?:img|svg|span|div)[^>]+\bclass\s*=\s*["'][^"']*(?:noPhoto|no-photo)[^"']*["'][^>]*""",
    re.I,
)
CANONICAL_RE = re.compile(r"""<link[^>]+rel=["']canonical["'][^>]+href=["']([^"']+)["']""", re.I)
SKU_RE = re.compile(r"""itemprop=["']sku["']\s+content=["']([^"']+)["']""", re.I)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")
CHALLENGE_HASH_RE = re.compile(r'const\s+defaultHash\s*=\s*"([^"]+)"')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=24)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--report", default=str(OUT_REPORT))
    return parser.parse_args()


def fetch_text(session: requests.Session, url: str, timeout: int) -> str:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def xml_locs(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text.encode("utf-8"))
    locs: list[str] = []
    for node in root.iter():
        if node.tag.endswith("loc") and node.text:
            locs.append(node.text.strip())
    return locs


def catalog_page_locs(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text.encode("utf-8"))
    locs: list[str] = []
    for url_node in root:
        if not url_node.tag.endswith("url"):
            continue
        for child in url_node:
            if child.tag.endswith("loc") and child.text:
                loc = child.text.strip()
                if loc.startswith(BASE_URL) and "/content/images/" not in loc:
                    locs.append(loc)
                break
    return locs


def load_product_urls(timeout: int) -> list[str]:
    session = requests.Session()
    session.headers.update(HEADERS)
    sitemap = fetch_text(session, SITEMAP_URL, timeout)
    locs = xml_locs(sitemap)
    product_urls: list[str] = []
    catalog_sitemaps = [url for url in locs if "catalog-sitemap" in url]
    for sitemap_url in catalog_sitemaps:
        xml_text = fetch_text(session, sitemap_url, timeout)
        product_urls.extend(catalog_page_locs(xml_text))
    return sorted(dict.fromkeys(product_urls))


def fetch_challenge_hash(timeout: int) -> str:
    session = requests.Session()
    session.headers.update(HEADERS)
    text = fetch_text(session, BASE_URL, timeout)
    match = CHALLENGE_HASH_RE.search(text)
    if not match:
        return ""
    return match.group(1)


def is_challenge_page(html: str) -> bool:
    return bool(CHALLENGE_HASH_RE.search(html) and "challenge_passed" in html and "location.reload" in html)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", value or "")).strip()


def extract_gallery_image(html: str) -> str:
    for match in IMG_TAG_RE.finditer(html):
        tag = match.group(0)
        class_match = CLASS_ATTR_RE.search(tag)
        if not class_match or "gallery__photo-img" not in class_match.group(1):
            continue
        src_match = SRC_ATTR_RE.search(tag)
        if src_match:
            return src_match.group(1).strip()
    return ""


def load_css_fallback_urls() -> set[str]:
    if not SPECIAL_UPLOAD_REPORT.exists() or not LIVE_MAP_CACHE.exists():
        return set()

    report = json.loads(SPECIAL_UPLOAD_REPORT.read_text(encoding="utf-8"))
    live_map = json.loads(LIVE_MAP_CACHE.read_text(encoding="utf-8"))
    url_by_article = {
        str(item.get("article") or "").strip(): str(item.get("url") or "").strip()
        for item in live_map.get("items", [])
        if str(item.get("article") or "").strip() and str(item.get("url") or "").strip()
    }

    fallback_urls: set[str] = set()
    for item in report.get("failed", []):
        article = str(item.get("article") or "").strip()
        if not article:
            continue
        image_path = GENERATED_IMAGES_ROOT.joinpath(*article.replace("\\", "/").split("/")) / "1.jpg"
        url = url_by_article.get(article)
        if image_path.exists() and url:
            fallback_urls.add(url.rstrip("/"))
    return fallback_urls


def make_session(challenge_hash: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    if challenge_hash:
        session.cookies.set("challenge_passed", challenge_hash, domain="vsedliarybalky.com.ua", path="/")
    return session


def analyze_product(
    url: str,
    challenge_hash: str,
    fallback_urls: set[str],
    timeout: int,
) -> dict:
    session = make_session(challenge_hash)
    started = time.time()
    result = {
        "url": url,
        "ok": False,
        "mode": "missing",
        "status_code": None,
        "article": None,
        "title": None,
        "image": None,
        "elapsed_ms": None,
    }
    try:
        response = session.get(url, timeout=timeout)
        result["status_code"] = response.status_code
        response.raise_for_status()
        html = response.text
        if is_challenge_page(html):
            match = CHALLENGE_HASH_RE.search(html)
            if match:
                session.cookies.set("challenge_passed", match.group(1), domain="vsedliarybalky.com.ua", path="/")
                response = session.get(url, timeout=timeout)
                result["status_code"] = response.status_code
                response.raise_for_status()
                html = response.text

        canonical_match = CANONICAL_RE.search(html)
        canonical_url = (canonical_match.group(1).rstrip("/") if canonical_match else url.rstrip("/"))
        sku_match = SKU_RE.search(html)
        h1_match = H1_RE.search(html)
        result["article"] = sku_match.group(1).strip() if sku_match else None
        result["title"] = clean_text(h1_match.group(1)) if h1_match else None

        image_src = extract_gallery_image(html)
        has_real_gallery = bool(image_src and "no-photo" not in image_src.lower() and "nophoto" not in image_src.lower())
        has_gallery_no_photo = bool(NO_PHOTO_GALLERY_RE.search(html))
        has_css_fallback = canonical_url in fallback_urls or url.rstrip("/") in fallback_urls

        if has_real_gallery:
            result.update({"ok": True, "mode": "html_gallery", "image": image_src})
        elif has_css_fallback:
            result.update({"ok": True, "mode": "css_fallback"})
        else:
            result.update({"ok": False, "mode": "missing_or_no_photo", "has_gallery_no_photo": has_gallery_no_photo})
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
    finally:
        result["elapsed_ms"] = int((time.time() - started) * 1000)
    return result


def summarize(results: Iterable[dict]) -> dict:
    items = list(results)
    html_gallery = [item for item in items if item.get("mode") == "html_gallery"]
    css_fallback = [item for item in items if item.get("mode") == "css_fallback"]
    missing = [item for item in items if not item.get("ok")]
    return {
        "total": len(items),
        "ok": len(html_gallery) + len(css_fallback),
        "html_gallery": len(html_gallery),
        "css_fallback": len(css_fallback),
        "missing": len(missing),
        "missing_sample": missing[:50],
    }


def main() -> int:
    args = parse_args()
    report_path = Path(args.report)
    urls = load_product_urls(args.timeout)
    if args.limit:
        urls = urls[: args.limit]

    challenge_hash = fetch_challenge_hash(args.timeout)
    fallback_urls = load_css_fallback_urls()

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        future_map = {
            executor.submit(analyze_product, url, challenge_hash, fallback_urls, args.timeout): url
            for url in urls
        }
        for future in as_completed(future_map):
            results.append(future.result())

    results.sort(key=lambda item: item["url"])
    payload = {
        "base_url": BASE_URL,
        "sitemap_url": SITEMAP_URL,
        "css_fallback_candidates": len(fallback_urls),
        "summary": summarize(results),
        "results": results,
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
