from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, ImageEnhance, ImageOps


ROOT = Path(r"D:\FISH\fish-sync")
ENV_FILE = ROOT / ".env"
OUT_DIR = ROOT / "public" / "site-category-assets"
REPORT = ROOT / "data" / "horoshop_category_visuals_report.json"


STOCK_ASSETS: dict[str, dict[str, str]] = {
    "home_hero": {
        "url": "https://images.unsplash.com/photo-1771357010303-dafdf16cc7e0?auto=format&fit=crop&w=1800&q=88",
        "source_page": "https://unsplash.com/photos/YZ4gx7yxx6g",
        "note": "fishing rods on dock, homepage hero",
    },
    "home_rods": {
        "url": "https://images.unsplash.com/photo-1650081484358-b338642813c0?auto=format&fit=crop&w=1400&q=86",
        "source_page": "https://unsplash.com/photos/Orr8PxPR820",
        "note": "fishing rod and reel detail",
    },
    "home_bait": {
        "url": "https://images.unsplash.com/photo-1707059833911-8a3ab7b396ec?auto=format&fit=crop&w=1400&q=86",
        "source_page": "https://unsplash.com/photos/ucTF1s-DMNo",
        "note": "fishing lure close-up",
    },
    "home_wide": {
        "url": "https://images.unsplash.com/photo-1770889439788-d3a06a6098df?auto=format&fit=crop&w=1800&q=86",
        "source_page": "https://unsplash.com/photos/two-people-ice-fishing-on-a-frozen-lake-4h9z_0mJ2Vc",
        "note": "winter fishing atmosphere",
    },
    "rod": {
        "url": "https://images.unsplash.com/photo-1650081484358-b338642813c0?auto=format&fit=crop&w=1200&q=84",
        "source_page": "https://unsplash.com/photos/Orr8PxPR820",
        "note": "rods, reels, rod accessories",
    },
    "reel": {
        "url": "https://images.unsplash.com/photo-1650081484358-b338642813c0?auto=format&fit=crop&w=1200&q=84",
        "source_page": "https://unsplash.com/photos/Orr8PxPR820",
        "note": "fishing reel close-up",
    },
    "line": {
        "url": "https://images.unsplash.com/photo-1505852679233-d9fd70aff56d?auto=format&fit=crop&w=1200&q=84",
        "source_page": "https://unsplash.com/photos/C_wIJQJPCmQ",
        "note": "angler reel and line mood image",
    },
    "hook": {
        "url": "https://images.unsplash.com/photo-1707059833911-8a3ab7b396ec?auto=format&fit=crop&w=1200&q=84",
        "source_page": "https://unsplash.com/photos/ucTF1s-DMNo",
        "note": "hook/lure detail",
    },
    "lure": {
        "url": "https://images.unsplash.com/photo-1707059833911-8a3ab7b396ec?auto=format&fit=crop&w=1200&q=84",
        "source_page": "https://unsplash.com/photos/ucTF1s-DMNo",
        "note": "lures and artificial bait",
    },
    "winter": {
        "url": "https://images.unsplash.com/photo-1770889439788-d3a06a6098df?auto=format&fit=crop&w=1200&q=84",
        "source_page": "https://unsplash.com/photos/two-people-ice-fishing-on-a-frozen-lake-4h9z_0mJ2Vc",
        "note": "winter fishing and ice-fishing categories",
    },
    "camp": {
        "url": "https://images.unsplash.com/photo-1723220766445-48ba1fd9bc11?auto=format&fit=crop&w=1200&q=84",
        "source_page": "https://unsplash.com/photos/a-group-of-chairs-and-a-table-under-a-tent-18_r4o4H9_E",
        "note": "outdoor chairs, camping and tourism",
    },
    "water": {
        "url": "https://images.unsplash.com/photo-1771357010303-dafdf16cc7e0?auto=format&fit=crop&w=1200&q=84",
        "source_page": "https://unsplash.com/photos/YZ4gx7yxx6g",
        "note": "generic fishing water scene",
    },
}


BANNER_MAP = {
    "home_hero": "home_hero",
    "home_rods": "home_rods",
    "home_bait": "home_bait",
    "home_wide": "home_wide",
}


SLUG_FAMILY_RULES: list[tuple[str, str]] = [
    ("zymov|lod|mormysh|zherlyts|motyl|sany|yashchyk|kostium|zhylka-zym", "winter"),
    ("turyzm|likhtar|posud|termos|plyty|horil|batareik|odia|vzutt|krisla|stiltsi|stoly", "camp"),
    ("kotush|reel", "reel"),
    ("vudylysh|spininh|fidern|koropovi|bolonsk|makhov|zapchastyny|kherabuna", "rod"),
    ("volosin|shnur|fliuor|povid|zhylka", "line"),
    ("hach|odynarn|triinyk|dviinyk|ofset", "hook"),
    ("prymank|vobler|bleshn|balansyr|mandula", "lure"),
    ("nasadoch|boil|pop-ap|dip|zernov|prykorm|pelets|fanatik|anvi|real-fish|interkril|makukha|tekhnoplankton|bounti|bum|puhach|rpf|keks", "lure"),
    ("montazh|karabin|vertliuh|kilts|kormush|hruzyla|osnashch|syhnal|mekhan|elektron|svinher|kyvok|pidstav|rod-pod", "hook"),
    ("pidsak|sadok|kukan", "water"),
    ("chokhl|sumk|orhanaiz|vidra|korobk|povodochn", "camp"),
    ("pva|instrument", "hook"),
    ("podarunkovi-sertyfikaty", "water"),
]


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


def fetch_live_category_slugs(base_url: str, timeout: int) -> list[str]:
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (compatible; fish-sync-category-visuals/1.0)"
    response = session.get(base_url, timeout=timeout)
    response.raise_for_status()
    match = re.search(r'defaultHash\s*=\s*"([^"]+)"', response.text)
    if match:
        host = urlparse(base_url).hostname or ""
        session.cookies.set("challenge_passed", match.group(1), domain=host, path="/")
        response = session.get(base_url, timeout=timeout)
        response.raise_for_status()

    ignored_prefixes = (
        "/blog/",
        "/checkout/",
        "/profile/",
        "/pro-nas/",
        "/oplata-i-dostavka/",
        "/obmin-ta-povernennya/",
        "/kontaktna-informatsiya/",
        "/store-reviews/",
        "/privacypolicy/",
        "/siteindex/",
    )
    links = sorted(set(re.findall(r'href="(/[a-z0-9\-{}]+/)"', response.text)))
    return [link for link in links if "{id}" not in link and not link.startswith(ignored_prefixes)]


def family_for_slug(slug: str) -> str:
    normalized = slug.strip("/")
    for pattern, family in SLUG_FAMILY_RULES:
        if re.search(pattern, normalized):
            return family
    return "water"


def download_asset(key: str, meta: dict[str, str], target: Path, timeout: int) -> dict:
    response = requests.get(meta["url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
    response.raise_for_status()
    target.parent.mkdir(parents=True, exist_ok=True)
    raw_path = target.with_suffix(".source.jpg")
    raw_path.write_bytes(response.content)

    image = Image.open(raw_path).convert("RGB")
    size = (1800, 720) if key.startswith("home_") else (1200, 840)
    image = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    image = ImageEnhance.Color(image).enhance(1.08)
    image = ImageEnhance.Contrast(image).enhance(1.07)
    image.save(target, "JPEG", quality=84, optimize=True, progressive=True)
    return {
        "source_url": meta["url"],
        "source_page": meta["source_page"],
        "note": meta["note"],
        "local_path": str(target),
        "source_size": Image.open(raw_path).size,
        "output_size": size,
    }


def admin_login(session: requests.Session, base_url: str, login: str, password: str, timeout: int) -> None:
    response = session.post(
        f"{base_url}/core-api/admin/security/login",
        json={"login": login, "password": password},
        timeout=timeout,
        verify=False,
    )
    response.raise_for_status()
    data = response.json()
    if int(data.get("status") or 0) != 200:
        raise RuntimeError(f"Horoshop auth failed: {data}")


def upload_asset(session: requests.Session, base_url: str, path: Path, timeout: int) -> dict:
    with path.open("rb") as fh:
        response = session.post(
            f"{base_url}/core-api/admin/app-json/upload-image",
            files={"file": (path.name, fh)},
            timeout=timeout,
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--skip-upload", action="store_true")
    args = parser.parse_args()

    env = load_env()
    base_url = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    login = env.get("HOROSHOP_LOGIN", "").strip()
    password = env.get("HOROSHOP_PASS", "").strip()
    if not args.skip_upload and (not login or not password):
        raise RuntimeError("HOROSHOP_LOGIN/HOROSHOP_PASS are missing in .env")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prepared = {}
    for key, meta in STOCK_ASSETS.items():
        prepared[key] = download_asset(key, meta, OUT_DIR / f"{key}.jpg", args.timeout)

    slugs = fetch_live_category_slugs(base_url, args.timeout)
    category_map = {slug: family_for_slug(slug) for slug in slugs}

    uploads = {}
    if not args.skip_upload:
        session = requests.Session()
        session.headers["User-Agent"] = "fish-sync-category-visuals/1.0"
        admin_login(session, base_url, login, password, args.timeout)
        uploads = {
            key: upload_asset(session, base_url, Path(info["local_path"]), args.timeout)
            for key, info in prepared.items()
        }

    report = {
        "base_url": base_url,
        "license_policy": {
            "provider": "Unsplash",
            "license_page": "https://unsplash.com/license",
            "reason": "free stock visuals used as decorative category/banner photos; no watermarks; no competitor product scraping",
        },
        "prepared": prepared,
        "uploads": uploads,
        "banner_map": BANNER_MAP,
        "category_map": category_map,
        "category_count": len(category_map),
        "family_counts": {family: list(category_map.values()).count(family) for family in sorted(set(category_map.values()))},
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"assets": len(prepared), "categories": len(category_map), "uploaded": len(uploads), "report": str(REPORT)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
