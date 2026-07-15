from __future__ import annotations

import argparse
import json
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin

import requests


ROOT = Path(r"D:\FISH\fish-sync")
DEFAULT_REPORT = ROOT / "data" / "horoshop_live_storefront_audit.json"
BASE_URL = "https://vsedliarybalky.com.ua"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "uk,en;q=0.9",
}

CHALLENGE_HASH_RE = re.compile(r'const\s+defaultHash\s*=\s*"([^"]+)"')
IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
SRC_RE = re.compile(r"""\bsrc\s*=\s*["']([^"']+)["']""", re.I)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")

PAGES = {
    "home": "/",
    "about": "/pro-nas/",
    "delivery": "/oplata-i-dostavka/",
    "returns": "/obmin-ta-povernennya/",
    "contacts": "/kontaktna-informatsiya/",
    "blog": "/blog/",
    "agreement": "/privacypolicy/",
    "reviews": "/store-reviews/",
}

OLD_MENU_LABELS = [
    "Кормушки",
    "Інструменти PVA",
    "Запчастини до вудилищ",
    "Звичайні гачки",
    "Фанатік",
    "Анві прикормка",
    "Реал Фіш",
    "Інтеркріл",
    "Анві пелетс",
    "Фанатік пелетс",
    "Боунті",
    "Бум",
    "РПФ",
    "Пугач",
]

EXPECTED_LABELS = [
    "Годівниці",
    "Інструменти",
    "Запчастини та аксесуари для вудок",
    "Fanatik",
    "Anvi",
    "Real Fish",
    "Interkril",
    "Bounty",
    "Boom",
    "RPF",
    "Puhach",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--product-limit", type=int, default=120)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--concurrency", type=int, default=24)
    return parser.parse_args()


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", value or "")).strip()


def visible_text(html: str) -> str:
    return clean_text(html)


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def get_with_challenge(session: requests.Session, url: str, timeout: int) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = session.get(url, timeout=timeout)
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt == 3:
                raise
            time.sleep(0.4 * attempt)
    else:
        raise last_exc or RuntimeError(f"Could not fetch {url}")
    match = CHALLENGE_HASH_RE.search(response.text)
    if match and "challenge_passed" in response.text and "location.reload" in response.text:
        session.cookies.set("challenge_passed", match.group(1), domain="vsedliarybalky.com.ua", path="/")
        for attempt in range(1, 4):
            try:
                response = session.get(url, timeout=timeout)
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(0.4 * attempt)
    return response


def img_sources(html: str) -> list[str]:
    sources: list[str] = []
    for tag in IMG_RE.findall(html):
        match = SRC_RE.search(tag)
        if match:
            sources.append(match.group(1).strip())
    return sources


def no_photo_count(html: str) -> int:
    lower = html.lower()
    return lower.count("nophoto") + lower.count("no-photo")


def page_audit(session: requests.Session, base_url: str, slug: str, timeout: int) -> dict:
    url = urljoin(base_url + "/", slug.lstrip("/"))
    started = time.time()
    item = {"url": url, "ok": False}
    try:
        response = get_with_challenge(session, url, timeout)
        html = response.text
        text = visible_text(html)
        h1 = clean_text(H1_RE.search(html).group(1)) if H1_RE.search(html) else ""
        title = clean_text(TITLE_RE.search(html).group(1)) if TITLE_RE.search(html) else ""
        images = img_sources(html)
        item.update(
            {
                "ok": response.status_code == 200,
                "status_code": response.status_code,
                "title": title,
                "h1": h1,
                "text_chars": len(text),
                "image_count": len(images),
                "no_photo_count": no_photo_count(html),
                "elapsed_ms": int((time.time() - started) * 1000),
            }
        )
    except Exception as exc:  # noqa: BLE001
        item.update({"error": str(exc), "elapsed_ms": int((time.time() - started) * 1000)})
    return item


def sitemap_locs(session: requests.Session, url: str, timeout: int) -> list[str]:
    response = get_with_challenge(session, url, timeout)
    response.raise_for_status()
    root = ET.fromstring(response.text.encode("utf-8"))
    return [node.text.strip() for node in root.iter() if node.tag.endswith("loc") and node.text]


def product_urls(session: requests.Session, base_url: str, timeout: int, limit: int) -> list[str]:
    locs = sitemap_locs(session, f"{base_url.rstrip('/')}/sitemap.xml", timeout)
    products: list[str] = []
    for sitemap in [loc for loc in locs if "catalog-sitemap" in loc]:
        for loc in sitemap_locs(session, sitemap, timeout):
            if loc.startswith(base_url) and "/content/images/" not in loc:
                products.append(loc)
    products = sorted(dict.fromkeys(products))
    return products[:limit] if limit else products


def product_audit(url: str, timeout: int) -> dict:
    session = make_session()
    started = time.time()
    item = {"url": url, "ok": False}
    try:
        response = get_with_challenge(session, url, timeout)
        html = response.text
        text = visible_text(html)
        images = img_sources(html)
        has_buy = any(word in text for word in ("Купити", "У кошик", "Замовити"))
        has_gallery = "gallery__photo-img" in html and no_photo_count(html) == 0
        item.update(
            {
                "ok": response.status_code == 200 and has_gallery and has_buy,
                "status_code": response.status_code,
                "h1": clean_text(H1_RE.search(html).group(1)) if H1_RE.search(html) else "",
                "has_gallery": has_gallery,
                "has_buy_action": has_buy,
                "image_count": len(images),
                "no_photo_count": no_photo_count(html),
                "elapsed_ms": int((time.time() - started) * 1000),
            }
        )
    except Exception as exc:  # noqa: BLE001
        item.update({"error": str(exc), "elapsed_ms": int((time.time() - started) * 1000)})
    return item


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    session = make_session()

    pages = {name: page_audit(session, base_url, slug, args.timeout) for name, slug in PAGES.items()}
    home_html = get_with_challenge(session, base_url, args.timeout).text
    home_text = visible_text(home_html)

    urls = product_urls(session, base_url, args.timeout, args.product_limit)
    products: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        future_map = {executor.submit(product_audit, url, args.timeout): url for url in urls}
        for future in as_completed(future_map):
            products.append(future.result())
    products.sort(key=lambda item: item["url"])

    missing_products = [item for item in products if not item.get("ok")]
    payload = {
        "base_url": base_url,
        "pages": pages,
        "menu": {
            "old_labels_present": [label for label in OLD_MENU_LABELS if label in home_text],
            "expected_labels_missing": [label for label in EXPECTED_LABELS if label not in home_text],
        },
        "home": {
            "image_count": len(img_sources(home_html)),
            "no_photo_count": no_photo_count(home_html),
            "has_catalog": "Каталог" in home_text,
            "has_cart": "кошик" in home_text.lower(),
        },
        "products_summary": {
            "checked": len(products),
            "ok": len(products) - len(missing_products),
            "bad": len(missing_products),
            "bad_sample": missing_products[:30],
        },
        "products": products,
    }
    Path(args.report).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ["menu", "home", "products_summary"]}, ensure_ascii=False, indent=2))
    print(f"Report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
