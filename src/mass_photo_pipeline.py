"""
mass_photo_pipeline.py

Downloads product images from the internet for backlog products,
processes them (autocontrast, saturation, square crop, 1080x1080),
and uploads to Horoshop.

Usage:
    python src/mass_photo_pipeline.py --limit 50 --dry-run   # test without upload
    python src/mass_photo_pipeline.py --limit 200             # first batch
    python src/mass_photo_pipeline.py                          # all remaining
    python src/mass_photo_pipeline.py --upload-only           # upload already-staged images
    python src/mass_photo_pipeline.py --reset-checkpoint      # restart from scratch
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import random
import re
import sys
import time
import traceback
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from PIL import Image, ImageEnhance, ImageOps
try:
    import numpy as _np
except ImportError:
    _np = None

ROOT = Path(r"D:\FISH\fish-sync")
BACKLOG_PATH = ROOT / "data" / "real_photo_backlog_20260531.json"
STAGING_DIR = ROOT / "public" / "mass-photo-staging"
UTILITY_DIR = ROOT / "public" / "mass-photo-utility"
CHECKPOINT_PATH = ROOT / "data" / "mass_photo_checkpoint.json"
REPORT_PATH = ROOT / "data" / "mass_photo_pipeline_report.json"
# Existing category images as fallback for generic products
CAT_ASSETS_DIR = ROOT / "public" / "site-category-assets-unique-all"
ENV_FILE = ROOT / ".env"

BASE_URL = "https://vsedliarybalky.com.ua"
CHECK_URL = f"{BASE_URL}/api/import-images/check"
ASSIGN_URL = f"{BASE_URL}/api/import-images/assign"

TARGET_SIZE = 1080
MIN_SOURCE_PX = 350
SEARCH_DELAY_MIN = 1.5   # seconds between searches (auto backend tolerates it)
SEARCH_DELAY_MAX = 3.0
RATE_LIMIT_BACKOFF = 45  # seconds to wait after a 403

FAMILY_LABELS_UK = {
    "spinning": "спінінгове вудилище",
    "carp_rod": "коропове вудилище",
    "bolognese_rod": "болонське вудилище",
    "float_rod": "махове вудилище",
    "feeder_rod": "фідерне вудилище",
    "feeder": "годівниця фідер",
    "hook": "гачок рибальський",
    "ready_rig": "готовий монтаж карп",
    "swivel": "вертлюг застібка рибалка",
    "weight": "грузило рибальське",
    "groundbait": "прикормка риболовля",
    "pellets": "пелетс карп",
    "pop_up_bait": "поп-ап бойл карп",
    "boilie": "бойл карповий",
    "pva_material": "PVA матеріал карп",
    "tools": "рибальський інструмент",
    "line": "волосінь рибальська",
    "fluorocarbon": "флюорокарбон ліска",
    "reel": "котушка рибальська",
    "chair": "крісло рибальське",
    "landing_net": "підсак рибальський",
    "keepnet": "садок рибальський",
    "silicone_lure": "силіконова приманка джиг",
    "wobbler": "воблер риболовля",
    "spinner": "блешня спінер",
    "float": "поплавок рибальський",
    "tackle_box": "коробка органайзер рибалка",
    "bag": "сумка рибальська",
    "cover": "чохол для вудилища",
    "jig_winter": "зимова приманка мармишка",
    "rod_rest_accessory": "підставка для вудилища",
    "mandula": "мандула приманка",
    "other": "рибальське спорядження",
}

# Category fallback images (family -> filename in site-category-assets-unique-all)
FAMILY_CAT_FALLBACK = {
    "hook": "cat_unique_hachky.jpg",
    "swivel": "cat_unique_vertliuhy_zastibky.jpg",
    "weight": "cat_unique_hruzyla.jpg",
    "ready_rig": "cat_unique_hotovi_montazhi.jpg",
    "float": "cat_unique_poplavky.jpg",
    "pva_material": "cat_unique_pva_materialy.jpg",
    "groundbait": "cat_unique_prykormka.jpg",
    "boilie": "cat_unique_boily.jpg",
    "pellets": "cat_unique_pelets.jpg",
    "pop_up_bait": "cat_unique_pop_up.jpg",
    "silicone_lure": "cat_unique_sylikonovi_prymanky.jpg",
    "wobbler": "cat_unique_voblery.jpg",
    "spinner": "cat_unique_bleshni.jpg",
    "line": "cat_unique_volosin.jpg",
    "reel": "cat_unique_kotushky.jpg",
    "spinning": "cat_unique_spininhy.jpg",
    "carp_rod": "cat_unique_koropovi.jpg",
    "float_rod": "cat_unique_makhovi.jpg",
    "feeder_rod": "cat_unique_fiderni.jpg",
    "cover": "cat_unique_chokhly.jpg",
    "landing_net": "cat_unique_pidsaky.jpg",
    "bag": "cat_unique_sumky_ta_korobky.jpg",
    "jig_winter": "cat_unique_aksesuary_zymovi.jpg",
    "tools": "cat_unique_aksesuary_do_kotushok.jpg",
}


# ── helpers ──────────────────────────────────────────────────────────────────

def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text("utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def admin_login(session: requests.Session, base_url: str, login: str, password: str) -> None:
    r = session.post(
        f"{base_url}/core-api/admin/security/login",
        json={"login": login, "password": password},
        timeout=30, verify=False,
    )
    r.raise_for_status()
    data = r.json()
    if int(data.get("status") or 0) != 200:
        raise RuntimeError(f"Horoshop login failed: {data}")


def fetch_tokens(session: requests.Session, base_url: str) -> dict[str, str]:
    r = session.get(
        f"{base_url}/core-api/admin/jwt/project-jwt/import-metadata",
        timeout=30, verify=False,
    )
    r.raise_for_status()
    data = r.json()
    metadata = ((data.get("payload") or {}).get("metadata") or {}) if isinstance(data, dict) else {}
    required = ("aws_endpoint", "project_jwt", "cloud_token")
    missing = [k for k in required if not metadata.get(k)]
    if missing:
        raise RuntimeError(f"Missing tokens: {missing}")
    return {k: str(metadata[k]) for k in required}


def get_tokens() -> dict[str, str]:
    env = load_env()
    base_url = (env.get("HOROSHOP_BASE_URL") or BASE_URL).rstrip("/")
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    admin_login(session, base_url, env.get("HOROSHOP_LOGIN", ""), env.get("HOROSHOP_PASS", ""))
    tokens = fetch_tokens(session, base_url)
    tokens["base_url"] = base_url
    return tokens


# ── search strategy ──────────────────────────────────────────────────────────

def clean_name_for_search(name_raw: str) -> str:
    """Strip size/variant specs to get a searchable core name."""
    n = name_raw.strip()
    # Remove trailing size specs
    n = re.sub(r"\s+\d+([.,]\d+)?\s*(м|мм|g|гр|kg|кг|lb|cm|см|pc|шт|mm|m|ft)(\b|$)", " ", n, flags=re.I)
    # Remove №N / #N / \N patterns
    n = re.sub(r"[№#\\]+\s*\d+([/\\]\d+)?", "", n)
    # Remove standalone numbers at end
    n = re.sub(r"\s+\d[\d\-./:*x×]+\s*$", "", n)
    # Remove trailing weight/size in parens
    n = re.sub(r"\s*\([^)]*\)\s*$", "", n)
    return re.sub(r"\s{2,}", " ", n).strip()


def is_generic_name(name_raw: str) -> bool:
    """Return True if product name is too generic for a useful search."""
    cleaned = clean_name_for_search(name_raw or "")
    # Generic if shorter than 5 chars after cleaning, or is just the family label
    generic_words = {"воблер", "гачок", "блешня", "ліска", "шнур", "вантаж",
                     "грузило", "поплавок", "котушка", "вудилище", "бойл"}
    words = set(cleaned.lower().split())
    return len(cleaned) < 6 or words <= generic_words


# Ukrainian/translit type words that must appear in a RELEVANT result title
FAMILY_MATCH_WORDS = {
    "spinning": ["спінінг", "спиннинг", "spinning", "вудилищ", "удилищ", "вудоч", "вудк"],
    "carp_rod": ["вудилищ", "удилищ", "коропов", "carp", "rod"],
    "bolognese_rod": ["болон", "вудилищ", "удилищ", "bolo"],
    "float_rod": ["вудоч", "вудилищ", "удоч", "удилищ", "махов", "болон", "pole"],
    "feeder_rod": ["фідер", "feeder", "вудилищ", "удилищ"],
    "feeder": ["фідер", "feeder", "годівниц", "кормушк"],
    "hook": ["гачок", "гачк", "крюч", "hook", "крючк"],
    "ready_rig": ["монтаж", "оснастк", "повід", "rig", "поводок"],
    "swivel": ["вертлюг", "застібк", "карабін", "swivel", "вертлюж"],
    "weight": ["грузил", "груз", "вантаж", "weight", "sinker"],
    "groundbait": ["прикорм", "підгодов", "groundbait", "підгодів"],
    "pellets": ["пелетс", "пелет", "pellet"],
    "pop_up_bait": ["поп-ап", "pop-up", "popup", "бойл", "boilie", "поп ап"],
    "boilie": ["бойл", "boilie"],
    "pva_material": ["pva", "пва"],
    "tools": ["інструмент", "інструменти"],
    "line": ["волосінь", "леск", "ліск", "шнур", "line", "плет", "флюорокарбон"],
    "fluorocarbon": ["флюорокарбон", "fluoro", "ліск", "волосінь"],
    "reel": ["котушк", "катушк", "reel"],
    "chair": ["крісл", "стіл", "стілец", "chair"],
    "landing_net": ["підсак", "підсач", "landing", "net"],
    "keepnet": ["садок", "садк", "keepnet"],
    "silicone_lure": ["силікон", "силикон", "приманк", "віброхвіст", "твістер", "twister", "lure", "слаг", "рак", "червяк", "личинк", "larva"],
    "wobbler": ["воблер", "wobbler", "приманк", "crank", "minnow"],
    "spinner": ["блешн", "блесн", "spinner", "spoon", "вертушк", "колебалк"],
    "float": ["поплав", "float"],
    "tackle_box": ["коробк", "органайзер", "box", "ящик"],
    "bag": ["сумк", "рюкзак", "чохол", "bag"],
    "cover": ["чохол", "тубус", "cover", "case"],
    "jig_winter": ["мормишк", "мармишк", "балда", "зимов", "jig", "приманк", "блешн"],
    "rod_rest_accessory": ["підставк", "тримач", "род-под", "rod pod", "бузбар", "тринаг"],
    "mandula": ["мандул", "mandula"],
    "other": [],
}

# Stop words excluded from product-token matching
_TOK_STOP = {"купити", "купить", "цена", "ціна", "грн", "uah", "для", "під", "the",
             "fishing", "рибалк", "риболовл", "набір", "набор", "new", "колір", "color",
             "цвет", "вес", "вага", "тест"}


def product_tokens(name_raw: str) -> list[str]:
    """Meaningful tokens (brand/model words) for relevance matching."""
    n = (name_raw or "").lower()
    n = re.sub(r"[^a-zа-яіїєґ0-9]+", " ", n)
    out = []
    for w in n.split():
        if len(w) < 3 or w in _TOK_STOP:
            continue
        if re.fullmatch(r"[0-9.,\-]+", w):  # pure number/size
            continue
        out.append(w)
    return out


def is_relevant(result: dict, prod_tokens: list[str], family: str) -> bool:
    """A result is relevant only if the result text shows the product type
    AND shares at least one distinctive product token (brand/model)."""
    hay = " ".join([
        result.get("title") or "",
        result.get("source") or "",
        result.get("url") or "",
    ]).lower()
    hay = re.sub(r"[^a-zа-яіїєґ0-9 ]+", " ", hay)
    fam_words = FAMILY_MATCH_WORDS.get(family, [])
    fam_ok = (not fam_words) or any(fw in hay for fw in fam_words)
    tok_hits = sum(1 for t in prod_tokens if t in hay)
    return fam_ok and tok_hits >= 1


def build_query(name_raw: str, family: str) -> str:
    """Build a search query: Ukrainian type word + brand/model tokens."""
    label = FAMILY_LABELS_UK.get(family, "рибалка")
    if is_generic_name(name_raw):
        return f"{label} купити"
    toks = product_tokens(name_raw)
    # prefer latin brand/model tokens (more reliable), then cyrillic
    latin = [t for t in toks if re.search(r"[a-z]", t)]
    cyr = [t for t in toks if not re.search(r"[a-z]", t)]
    ordered = (latin + cyr)[:5]
    if not ordered:
        return f"{label} купити"
    return f"{label} {' '.join(ordered)} купити"


# Keywords suggesting fishing/sporting goods product image sources
FISHING_KEYWORDS = [
    "prom.ua", "rozetka", "fishing", "fish", "carp", "spin", "angl",
    "tackle", "bait", "lure", "hook", "rod", "reel",
    "rybalk", "rybalka", "rybak", "рибалк", "рыбалк",
    "allegro", "ozon", "amazon", "ebay", "aliexpress", "ali",
    "fanatik", "flagman", "kalipso", "brain", "weida", "mifine",
    "shimano", "daiwa", "mustad", "owner", "gamakatsu", "rapala",
    "coolcarp", "fenixcarp", "trinitybaits", "carpshop",
    "sport", "outdoor", "hunt", "tactic", "snast",
    "content/images", "product", "/goods/", "/catalog/",
]

# Keywords that should NEVER appear in product image URLs
BLOCKED_KEYWORDS = [
    "hotel", "booking", "tripadvisor", "airbnb", "restaurant", "cafe",
    "instagram", "facebook", "twitter", "pinterest", "tiktok",
    "wikipedia", "news", "blog", "forum", "fazenda", "resort",
    "shutterstock", "gettyimages", "istockphoto", "dreamstime",
    "allsaopaulohotels", "klimaleichtblock", "baumarkt", "haus",
    "academia", "university", "library",
    "reddit", "redd.it", "imgur", "tumblr", "flickr",
    "ynet", "ynetnews", "bbc", "cnn", "nytimes",
    "preview.redd", "i.redd", "external-preview",
]

# File extensions that are definitely not product images
BAD_EXTENSIONS = [".svg", ".gif", ".ico", ".pdf", ".webm"]


def is_russian_source(url: str) -> bool:
    u = url.lower()
    return any(b in u for b in RU_BLOCKED)


def is_good_url(url: str) -> bool:
    """True if URL could be a product image (not hotel/social/stock/Russian)."""
    url_lower = url.lower()
    if is_russian_source(url_lower):
        return False
    for bad in BLOCKED_KEYWORDS:
        if bad in url_lower:
            return False
    for ext in BAD_EXTENSIONS:
        if url_lower.endswith(ext):
            return False
    return True


# Trusted UA retailers / brand / neutral sites with CLEAN photos (no overlays).
# NO Russian sources (policy: не качати з руських).
CLEAN_SOURCES = [
    "rozetka", "content.rozetka", "goldencatch", "cdn.27.ua", "epicentrk",
    "epicentr", "twitchfishing", "fishingklad", "carpan", "ua.fish",
    "fenixcarp", "trinitybaits", "coolcarp", "slovi.com",
    "daiwa", "favorite", "flagman.ua", "brain", "fishelement",
    "clubfish", "world4carp", "globalfishing", "kalipso",
    "allegroimg", "aliexpress", "alicdn", "made-in-china", "ebayimg",
    "fanatik.com.ua", "atbmarket", "zakaz.atbmarket",
    "spinningline.com.ua", "tackledirect",
]
# Russian domains — never download (policy). Checked before everything.
RU_BLOCKED = [
    ".ru/", "ozon", "ozone", "wildberries", "wbstatic", "wb.ru", "yandex",
    "sportmaster.ru", "carpomaniya", "avito", "satu.kz", "tiu.ru",
    "megabit", "fmagazin.ru", ".ru?", "//ir.", "carpfishing.ru",
]
# Domains/markers that frequently carry seller text/logo watermarks — avoid
WATERMARK_PRONE_SOURCES = [
    "prom.ua", "images.prom", "olx", "bigl.ua", "deshevle", "dilf",
    "zakupka", "ua-region", "fishfish", "fish-fish", "f.ua", "shafa",
    "rybalka.com", "klevok", "ribalka",
    # shops that stamp big competitor watermarks
    "shimano.kiev", ".kiev.ua", "kiev.ua", "shimano-", "fmagazin",
    "spinningov", "rybolov", "sportsman", "decathlon",
]

# TOP-TIER clean retailers — never add seller text watermarks, have generic
# photos for every product type. Used to build family pools (the multiplier).
TOPTIER_CLEAN = [
    "rozetka", "content.rozetka", "epicentr", "cdn.27.ua", "goldencatch",
    "aliexpress", "alicdn", "allegroimg", "ebayimg", "made-in-china",
]


def is_toptier_clean(url: str) -> bool:
    u = url.lower()
    if any(b in u for b in RU_BLOCKED) or any(w in u for w in WATERMARK_PRONE_SOURCES):
        return False
    return any(t in u for t in TOPTIER_CLEAN)


def url_score_bonus(url: str) -> float:
    """Score URL by source cleanliness + product-path markers.
    Clean retailers win strongly; watermark-prone shops are heavily penalized."""
    u = url.lower()
    score = 0.0
    if any(c in u for c in CLEAN_SOURCES):
        score += 1.2
    elif any(w in u for w in WATERMARK_PRONE_SOURCES):
        score -= 1.0          # strongly deprioritized (often watermarked)
    elif any(kw in u for kw in FISHING_KEYWORDS):
        score += 0.3
    else:
        score -= 0.4          # unknown small shop — likely watermarked, avoid
    product_markers = ["/images/", "/img/", "/product", "/goods", "/catalog", "/foto", "content", "/storage/"]
    if not any(m in u for m in product_markers):
        score -= 0.1
    return score


def red_watermark_ratio(path: Path) -> float:
    """Fraction of strongly-saturated red pixels (seller text overlays like
    'Безкоштовна доставка', 'АКЦІЯ', phone numbers). High => likely watermark."""
    if _np is None:
        return 0.0
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((400, 400))
            a = _np.asarray(im).astype(int)
        R, G, B = a[..., 0], a[..., 1], a[..., 2]
        red = (R > 150) & (R - G > 70) & (R - B > 70)
        return float(red.mean())
    except Exception:
        return 0.0


WATERMARK_RED_THRESHOLD = 0.013  # above this => reject as watermarked


def ddg_image_search(query: str, min_px: int = MIN_SOURCE_PX, retries: int = 2) -> list[dict]:
    """Search images via ddgs multi-engine 'auto' backend (Bing/Google/DDG/...).
    Robust against single-engine rate limits. Retries because 'auto' rotates
    engines — a retry often lands on a healthy engine with good results."""
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS

    best: list[dict] = []
    for attempt in range(retries):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.images(
                    query,
                    safesearch="off",
                    max_results=15,
                    backend="auto",
                ))
            filtered = [r for r in results
                        if int(r.get("width") or 0) >= min_px
                        and int(r.get("height") or 0) >= min_px
                        and is_good_url(r.get("image", ""))]
            if len(filtered) > len(best):
                best = filtered
            # Good enough — stop early
            if len(filtered) >= 4:
                return filtered
            time.sleep(0.8)  # brief pause, then retry rotates engine
        except Exception as exc:
            err = str(exc)
            if "403" in err or "Ratelimit" in err or "ratelimit" in err:
                wait = RATE_LIMIT_BACKOFF * (attempt + 1)
                print(f"  DDG rate limit, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  search error: {exc}")
                break
    return best


def _score(r: dict) -> float:
    w, h = int(r.get("width") or 1), int(r.get("height") or 1)
    ratio = w / h
    squareness = 1.0 - abs(1.0 - ratio) * 0.5
    size_score = min(w, h) / 1200.0
    src = r.get("image", "")
    bonus = url_score_bonus(src)
    penalty = 0.3 if any(x in src for x in ["thumbnail", "small", "mini"]) else 0
    return squareness + size_score + bonus - penalty


def is_clean_source(url: str) -> bool:
    """True only for big trusted retailers / brand sites with clean photos.
    Watermark-prone shops (prom, dilf, olx, unknown small shops) are excluded
    so exact-match photos never carry seller watermarks (user policy)."""
    u = url.lower()
    if any(w in u for w in WATERMARK_PRONE_SOURCES):
        return False
    return any(c in u for c in CLEAN_SOURCES)


def pick_relevant_images(results: list[dict], prod_tokens: list[str],
                         family: str) -> list[str]:
    """Return RELEVANT image URLs from CLEAN sources only, best first.
    Empty if no clean-source relevant match (-> caller uses family pool)."""
    relevant = [r for r in results
                if is_relevant(r, prod_tokens, family)
                and is_clean_source(r.get("image", ""))]
    relevant.sort(key=_score, reverse=True)
    return [r["image"] for r in relevant]


def pick_relevant_images_any(results: list[dict], prod_tokens: list[str],
                             family: str) -> list[str]:
    """RELEVANT URLs from ANY non-Russian source (incl. watermark-prone shops).
    Used for niche products with no clean source: we take the REAL product photo
    and cover the seller watermark with our own logo."""
    relevant = [r for r in results
                if is_relevant(r, prod_tokens, family)
                and not is_russian_source(r.get("image", ""))]
    relevant.sort(key=_score, reverse=True)
    return [r["image"] for r in relevant]


# ── image download ────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}


def download_image(url: str, dest: Path) -> bool:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20, stream=True)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        with Image.open(dest) as img:
            w, h = img.size
            if min(w, h) < MIN_SOURCE_PX:
                dest.unlink(missing_ok=True)
                return False
        return True
    except Exception:
        dest.unlink(missing_ok=True)
        return False


# ── image processing ──────────────────────────────────────────────────────────

LOGO_PATH = ROOT / "public" / "site-assets" / "logo-full.png"  # complete fish+text
_LOGO_CACHE: dict = {}


def _logo_rgba():
    if "img" not in _LOGO_CACHE:
        _LOGO_CACHE["img"] = Image.open(LOGO_PATH).convert("RGBA")
    return _LOGO_CACHE["img"]


def reduce_watermark(img: Image.Image) -> Image.Image:
    """Best-effort reduction of a competitor's semi-transparent text watermark
    via cv2 inpaint over detected light low-saturation text strokes (the same
    library approach as the first pass). Gentle: only thin strokes, preserves
    the product. Not 100% but removes most of the overlay."""
    if _np is None:
        return img
    try:
        import cv2 as _cv
    except Exception:
        return img
    bgr = _cv.cvtColor(_np.array(img.convert("RGB")), _cv.COLOR_RGB2BGR)
    h, w = bgr.shape[:2]
    gray = _cv.cvtColor(bgr, _cv.COLOR_BGR2GRAY)
    hsv = _cv.cvtColor(bgr, _cv.COLOR_BGR2HSV)
    blur = _cv.GaussianBlur(gray, (0, 0), 3)
    resid = _cv.normalize(_cv.absdiff(gray, blur), None, 0, 255, _cv.NORM_MINMAX)
    # watermark text strokes: high-freq + light + low-saturation
    strokes = ((resid > 18) & (gray > 150) & (hsv[..., 1] < 70)).astype("uint8") * 255
    # keep only stroke clusters that line up horizontally (text), drop product specks
    strokes = _cv.morphologyEx(strokes, _cv.MORPH_CLOSE,
                               _cv.getStructuringElement(_cv.MORPH_RECT, (25, 1)), iterations=1)
    if int((strokes > 0).sum()) < w * 3:
        return img
    mask = _cv.dilate(strokes, _np.ones((3, 3), "uint8"), iterations=1)
    out = _cv.inpaint(bgr, mask, 3, _cv.INPAINT_TELEA)
    return Image.fromarray(_cv.cvtColor(out, _cv.COLOR_BGR2RGB))


def apply_logo(img: Image.Image, mode: str = "subtle") -> Image.Image:
    """Overlay shop logo (complete logo, always kept inside the frame).
    - 'subtle': small, bottom-right, ~30% (clean photos — branding)
    - 'cover' : larger, centered, ~45% (niche photos)."""
    if mode == "none":
        return img
    import numpy as _n
    W, H = img.size
    logo = _logo_rgba()
    if mode == "cover":
        wf, opacity = 0.50, 0.42
    else:
        wf, opacity = 0.24, 0.30
    lw = int(W * wf); lh = int(lw * logo.height / logo.width)
    mx = int(W * 0.035)
    if mode == "cover":
        x0, y0 = (W - lw) // 2, (H - lh) // 2          # centered, fully inside
    else:
        x0, y0 = W - lw - mx, H - lh - mx              # bottom-right with margin
    x0 = max(0, min(x0, W - lw)); y0 = max(0, min(y0, H - lh))
    la = _n.array(logo.resize((lw, lh), Image.LANCZOS)).astype(float)
    al = (la[..., 3] / 255.0) * opacity
    base = _n.array(img.convert("RGB")).astype(float)
    roi = base[y0:y0 + lh, x0:x0 + lw]
    shadow = _n.roll(_n.roll(al, 2, 0), 2, 1) * 0.55
    for c in range(3):
        roi[..., c] = roi[..., c] * (1 - shadow)
    for c in range(3):
        roi[..., c] = roi[..., c] * (1 - al) + 245 * al
    base[y0:y0 + lh, x0:x0 + lw] = roi
    return Image.fromarray(_n.clip(base, 0, 255).astype("uint8"), "RGB")


def process_image(src: Path, dest: Path, edge_trim: float = 0.06,
                  logo_mode: str = "subtle") -> bool:
    """
    Process: RGB -> edge trim -> autocontrast -> saturation x1.18 ->
    center square crop -> 1080x1080 -> overlay shop logo -> JPEG q=87.
    logo_mode: 'subtle' (clean), 'cover' (niche/watermarked), 'none'.
    """
    try:
        with Image.open(src) as raw:
            img = raw.convert("RGB")
        w, h = img.size
        if edge_trim > 0 and min(w, h) > 200:
            dx, dy = int(w * edge_trim), int(h * edge_trim)
            img = img.crop((dx, dy, w - dx, h - dy))
        img = ImageOps.autocontrast(img, cutoff=0.5)
        img = ImageEnhance.Color(img).enhance(1.18)
        w, h = img.size
        m = min(w, h)
        img = img.crop(((w - m) // 2, (h - m) // 2, (w + m) // 2, (h + m) // 2))
        img = img.resize((TARGET_SIZE, TARGET_SIZE), Image.LANCZOS)
        if logo_mode == "cover":
            img = reduce_watermark(img)     # strip competitor watermark first
        img = apply_logo(img, logo_mode)
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, "JPEG", quality=87, optimize=True)
        return True
    except Exception as exc:
        print(f"  process_image error {src.name}: {exc}")
        return False


# ── Horoshop upload ───────────────────────────────────────────────────────────

def horoshop_upload_one(article: str, processed_path: Path, tokens: dict) -> dict:
    filename = processed_path.name
    session = requests.Session()
    # Check
    try:
        r = session.post(
            CHECK_URL,
            headers={"Authorization": f"Bearer {tokens['project_jwt']}",
                     "Content-Type": "application/json"},
            json={"images": [filename]},
            timeout=30,
        )
        r.raise_for_status()
        check_data = r.json()["response"]["data"]
    except Exception as exc:
        return {"article": article, "status": "check_failed", "error": str(exc)}

    image_meta = check_data.get(filename, {})
    if not image_meta.get("success"):
        return {"article": article, "status": "check_rejected",
                "reason": image_meta.get("message", "unknown")}
    # Upload
    try:
        mime = mimetypes.guess_type(filename)[0] or "image/jpeg"
        with processed_path.open("rb") as fh:
            r2 = session.post(
                f"{tokens['aws_endpoint']}/upload_images/upload-image",
                headers={"Authorization": f"Bearer {tokens['cloud_token']}"},
                data={"projectUuid": image_meta.get("projectUuid") or "",
                      "awsKey": image_meta.get("awsKey") or ""},
                files={"file": (filename, fh, mime)},
                timeout=60,
            )
        r2.raise_for_status()
        upload_item = r2.json()["data"]["items"][0]
    except Exception as exc:
        return {"article": article, "status": "upload_failed", "error": str(exc)}
    # Assign
    try:
        r3 = session.post(
            ASSIGN_URL,
            headers={"Authorization": f"Bearer {tokens['project_jwt']}",
                     "Content-Type": "application/json"},
            json={"images": [upload_item], "cleanGallery": True},
            timeout=30,
        )
        r3.raise_for_status()
        return {"article": article, "status": "uploaded"}
    except Exception as exc:
        return {"article": article, "status": "assign_failed", "error": str(exc)}


# ── checkpoint ────────────────────────────────────────────────────────────────

def load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        try:
            return json.loads(CHECKPOINT_PATH.read_text("utf-8"))
        except Exception:
            pass
    return {"done": {}, "search_failed": [], "upload_failed": []}


def save_checkpoint(cp: dict) -> None:
    CHECKPOINT_PATH.write_text(json.dumps(cp, ensure_ascii=False, indent=2), "utf-8")


# ── grouping ──────────────────────────────────────────────────────────────────

def group_key(item: dict) -> str:
    """
    Group key for deduplication:
    - Use first 4 words of name_raw (removes size/color variants)
    - Fall back to source_category if name is very generic
    """
    name = (item.get("name_raw") or "").strip()
    if is_generic_name(name):
        # Group all generic items by family+source_category
        return f"__generic__{item.get('family', 'other')}__{item.get('source_category', '')}"
    # Take first 4 words as key
    words = re.sub(r"[^\w\s]", " ", name.lower()).split()
    return " ".join(words[:4])


def group_items(items: list[dict]) -> list[tuple[str, list[dict]]]:
    """Group backlog items, returns sorted list of (key, items)."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        groups[group_key(item)].append(item)
    # Sort: specific products first (non-generic), then generic fallbacks
    specific = [(k, v) for k, v in groups.items() if not k.startswith("__generic__")]
    generic = [(k, v) for k, v in groups.items() if k.startswith("__generic__")]
    return sorted(specific) + sorted(generic)


# ── family real-photo pool (replaces category banners) ────────────────────────
# For products with no exact brand match we use REAL photos of that product
# TYPE (a real spinning rod, a real wobbler...) — never a category banner.

FAMILY_POOL_DIR = ROOT / "public" / "family-photo-pool"
# Search phrases that return real product photos of each family type
FAMILY_POOL_QUERIES = {
    "spinning": "спінінгове вудилище риболовля",
    "carp_rod": "коропове вудилище carp rod",
    "bolognese_rod": "болонське вудилище",
    "float_rod": "махове вудилище поплавкове",
    "feeder_rod": "фідерне вудилище feeder rod",
    "feeder": "годівниця фідерна кормушка",
    "hook": "рибальський гачок hook",
    "ready_rig": "готовий повідець монтаж карповий",
    "swivel": "вертлюг застібка рибальський",
    "weight": "грузило рибальське",
    "groundbait": "прикормка рибальська пакет",
    "pellets": "пелетс рибальський pellets",
    "pop_up_bait": "поп-ап бойли pop-up",
    "boilie": "бойли карпові boilie",
    "pva_material": "pva пакет сітка карп",
    "tools": "рибальський інструмент",
    "line": "волосінь рибальська шпуля",
    "fluorocarbon": "флюорокарбон рибальський",
    "reel": "котушка рибальська reel",
    "chair": "крісло коропове рибальське",
    "landing_net": "підсак рибальський",
    "keepnet": "садок рибальський",
    "silicone_lure": "силіконова приманка віброхвіст",
    "wobbler": "воблер рибальський wobbler",
    "spinner": "блешня вертушка рибальська",
    "float": "поплавок рибальський",
    "tackle_box": "рибальська коробка органайзер",
    "bag": "рибальська сумка чохол",
    "cover": "чохол для вудилища тубус",
    "jig_winter": "зимова мормишка приманка",
    "rod_rest_accessory": "підставка для вудилища род-под",
    "mandula": "мандула приманка рибальська",
    "other": "рибальське спорядження снасті",
}

# in-memory pools: family -> {"paths": [Path,...], "idx": int}
_FAMILY_POOLS: dict[str, dict] = {}


def is_relevant_relaxed(result: dict, family: str) -> bool:
    """Relaxed: only require the product TYPE word to appear (no brand token).
    Used to fetch a real photo of the product type when no exact match exists."""
    hay = " ".join([result.get("title") or "", result.get("source") or "",
                    result.get("url") or ""]).lower()
    hay = re.sub(r"[^a-zа-яіїєґ0-9 ]+", " ", hay)
    fam_words = FAMILY_MATCH_WORDS.get(family, [])
    return (not fam_words) or any(fw in hay for fw in fam_words)


def ensure_family_pool(family: str, want: int = 8) -> list[Path]:
    """Download up to `want` clean REAL photos of this product type once,
    cache on disk + memory, return list of paths."""
    if family in _FAMILY_POOLS and _FAMILY_POOLS[family]["paths"]:
        return _FAMILY_POOLS[family]["paths"]

    pool_dir = FAMILY_POOL_DIR / family
    pool_dir.mkdir(parents=True, exist_ok=True)
    # reuse already-downloaded pool files
    existing = sorted(pool_dir.glob("*.jpg"))
    if len(existing) >= want:
        _FAMILY_POOLS[family] = {"paths": existing, "idx": 0}
        return existing

    query = FAMILY_POOL_QUERIES.get(family, FAMILY_LABELS_UK.get(family, "рибалка") + " риболовля")
    print(f"  [pool] building real-photo pool for '{family}': {query}")
    results = ddg_image_search(query)
    # relaxed relevance (type word present) + CLEAN source only (no watermarks)
    cands = [r for r in results
             if is_relevant_relaxed(r, family) and is_clean_source(r.get("image", ""))]
    if not cands:  # nothing clean — fall back to relaxed (still type-correct)
        cands = [r for r in results if is_relevant_relaxed(r, family)]
    cands.sort(key=_score, reverse=True)

    paths = list(existing)
    n = len(paths)
    for r in cands:
        if len(paths) >= want:
            break
        tmp = pool_dir / f"pool_{n}.jpg"
        if download_image(r["image"], tmp):
            if red_watermark_ratio(tmp) < WATERMARK_RED_THRESHOLD:
                paths.append(tmp)
                n += 1
            else:
                tmp.unlink(missing_ok=True)
    _FAMILY_POOLS[family] = {"paths": paths, "idx": 0}
    print(f"  [pool] '{family}': {len(paths)} real photos ready")
    return paths


def next_family_photo(family: str) -> Path | None:
    """Round-robin a real photo from the family pool.
    Falls back to the generic 'other' pool so no product is ever left blank."""
    paths = ensure_family_pool(family)
    if not paths and family != "other":
        paths = ensure_family_pool("other")
        family = "other"
    if not paths:
        return None
    st = _FAMILY_POOLS[family]
    p = paths[st["idx"] % len(paths)]
    st["idx"] += 1
    return p


# ── main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0, help="Process N groups (0=all)")
    p.add_argument("--offset", type=int, default=0, help="Skip first N groups")
    p.add_argument("--dry-run", action="store_true", help="No upload")
    p.add_argument("--upload-only", action="store_true", help="Only upload staged")
    p.add_argument("--concurrency", type=int, default=2, help="Upload concurrency")
    p.add_argument("--reset-checkpoint", action="store_true")
    p.add_argument("--generic-only", action="store_true",
                   help="Only process generic-name products (use category fallback)")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    backlog = json.loads(BACKLOG_PATH.read_text("utf-8"))
    items = backlog.get("items", [])
    print(f"Backlog: {len(items)} products")

    cp = {} if args.reset_checkpoint else load_checkpoint()
    done_articles: dict = cp.get("done", {})
    search_failed: list = cp.get("search_failed", [])
    upload_failed: list = cp.get("upload_failed", [])

    # Filter already-done
    items = [it for it in items if it["article"] not in done_articles]
    print(f"Remaining: {len(items)}")

    groups = group_items(items)
    pending = [(k, v) for k, v in groups if any(a["article"] not in done_articles for a in v)]

    if args.generic_only:
        pending = [(k, v) for k, v in pending if k.startswith("__generic__")]
        print(f"Generic-only mode: {len(pending)} groups")

    if args.offset:
        pending = pending[args.offset:]
    if args.limit:
        pending = pending[:args.limit]

    print(f"Groups to process: {len(pending)}")

    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    UTILITY_DIR.mkdir(parents=True, exist_ok=True)

    stats = dict(searched=0, downloaded=0, processed=0, category_fallback=0,
                 uploaded=0, search_fail=0, download_fail=0, process_fail=0, upload_fail=0)

    to_upload: dict[str, Path] = {}  # article -> processed path

    # ── Phase 1: Search + Download + Process ─────────────────────────────────
    if not args.upload_only:
        for idx, (key, group) in enumerate(pending, 1):
            articles = [it["article"] for it in group if it["article"] not in done_articles]
            if not articles:
                continue

            rep = max(group, key=lambda x: len(x.get("name_raw") or ""))
            name_raw = rep.get("name_raw") or ""
            family = rep.get("family") or "other"
            is_generic = key.startswith("__generic__")

            print(f"\n[{idx}/{len(pending)}] '{name_raw[:60]}' ({len(articles)} articles)")

            # --- Generic products: real photo of the product TYPE (pool) ---
            if is_generic:
                got_any = False
                for article in articles:
                    dest = UTILITY_DIR / f"{article}@gallery_common.jpg"
                    if not dest.exists():
                        src = next_family_photo(family)
                        if src and process_image(src, dest):
                            stats["processed"] += 1
                            stats["category_fallback"] += 1
                        else:
                            stats["process_fail"] += 1
                            continue
                    to_upload[article] = dest
                    got_any = True
                if not got_any:
                    print(f"  No pool photo for family={family}, skipping")
                    search_failed.extend(articles)
                continue

            # --- Specific products: search online with RELEVANCE validation ---
            staged = STAGING_DIR / f"{articles[0]}_raw.jpg"
            prod_tokens = product_tokens(name_raw)
            logo_mode = "subtle"   # clean photo -> subtle corner logo

            if not staged.exists():
                # Gather relevant candidates from up to 2 query variants
                relevant_urls: list[str] = []
                query = build_query(name_raw, family)
                print(f"  Search: {query}")
                results = ddg_image_search(query)
                stats["searched"] += 1
                relevant_urls = pick_relevant_images(results, prod_tokens, family)

                if not relevant_urls:
                    # Retry: brand tokens only (no family word) — sometimes title
                    # lacks the type word but is the right product page
                    latin = [t for t in prod_tokens if re.search(r"[a-z]", t)]
                    if latin:
                        q2 = f"{' '.join(latin[:5])} {FAMILY_LABELS_UK.get(family,'')} купити".strip()
                        if q2 != query:
                            print(f"  Retry: {q2}")
                            results2 = ddg_image_search(q2)
                            stats["searched"] += 1
                            relevant_urls = pick_relevant_images(results2, prod_tokens, family)

                # Tier 2: no CLEAN source -> take REAL product photo from ANY
                # (non-Russian) source and cover the seller watermark with our logo.
                any_urls: list[str] = []
                if not relevant_urls:
                    any_urls = pick_relevant_images_any(results, prod_tokens, family)
                    if not relevant_urls and 'results2' in dir() and results2:
                        any_urls += pick_relevant_images_any(results2, prod_tokens, family)

                if not relevant_urls and not any_urls:
                    # No real photo anywhere → REAL photo of product TYPE (pool)
                    print(f"  No match anywhere -> real-type photo (pool)")
                    got_any = False
                    for article in articles:
                        dest = UTILITY_DIR / f"{article}@gallery_common.jpg"
                        if not dest.exists():
                            src = next_family_photo(family)
                            if src and process_image(src, dest, logo_mode="subtle"):
                                stats["category_fallback"] += 1
                                stats["processed"] += 1
                            else:
                                stats["process_fail"] += 1
                                continue
                        to_upload[article] = dest
                        got_any = True
                    if not got_any:
                        search_failed.extend(articles)
                        stats["search_fail"] += len(articles)
                    cp.update({"search_failed": search_failed})
                    save_checkpoint(cp)
                    time.sleep(random.uniform(SEARCH_DELAY_MIN, SEARCH_DELAY_MAX))
                    continue

                if not relevant_urls and any_urls:
                    # real product from a watermark-prone shop -> cover with logo
                    relevant_urls = any_urls
                    logo_mode = "cover"
                    print(f"  No clean source -> REAL photo + logo cover ({len(any_urls)} cand)")

                # Download relevant candidates, pick the cleanest (no watermark)
                ok = False
                best_red = 1.0
                tmp = STAGING_DIR / f"{articles[0]}_try.jpg"
                for u in relevant_urls[:6]:
                    if not download_image(u, tmp):
                        continue
                    red = red_watermark_ratio(tmp)
                    if red < best_red:
                        best_red = red
                        tmp.replace(staged)  # keep best-so-far as staged
                        ok = True
                        if red < WATERMARK_RED_THRESHOLD:
                            print(f"  Downloaded CLEAN (red={red:.3f}): {u[:60]}")
                            break
                        else:
                            print(f"  candidate watermarked (red={red:.3f}), trying next")
                    else:
                        tmp.unlink(missing_ok=True)
                if tmp.exists():
                    tmp.unlink(missing_ok=True)

                if ok and best_red >= WATERMARK_RED_THRESHOLD:
                    print(f"  best available has red={best_red:.3f} (kept)")

                if ok:
                    stats["downloaded"] += 1
                else:
                    print(f"  All relevant downloads failed -> real-type photo (pool)")
                    stats["download_fail"] += 1
                    logo_mode = "subtle"
                    src = next_family_photo(family)
                    if src:
                        staged = src
                    else:
                        search_failed.extend(articles)
                        cp.update({"search_failed": search_failed})
                        save_checkpoint(cp)
                        time.sleep(random.uniform(SEARCH_DELAY_MIN, SEARCH_DELAY_MAX))
                        continue

                time.sleep(random.uniform(SEARCH_DELAY_MIN, SEARCH_DELAY_MAX))

            else:
                print(f"  Using cached download")

            # Process for each article (logo_mode: subtle=clean, cover=watermarked)
            for article in articles:
                dest = UTILITY_DIR / f"{article}@gallery_common.jpg"
                if dest.exists():
                    to_upload[article] = dest
                    continue
                ok = process_image(staged, dest, logo_mode=logo_mode)
                if ok:
                    print(f"  {article}: processed ({logo_mode})")
                    stats["processed"] += 1
                    to_upload[article] = dest
                else:
                    print(f"  {article}: process FAILED")
                    stats["process_fail"] += 1

        print(f"\nPhase 1 done: {stats['processed']} processed, {len(to_upload)} queued for upload")

    else:
        # upload-only: scan for processed images not yet uploaded
        print("Upload-only: scanning utility dir...")
        for f in sorted(UTILITY_DIR.glob("*@gallery_common.jpg")):
            article = f.stem.split("@")[0]
            if article not in done_articles:
                to_upload[article] = f
        print(f"  Found {len(to_upload)} images to upload")

    # ── Phase 2: Upload ───────────────────────────────────────────────────────
    if to_upload and not args.dry_run:
        print(f"\nUploading {len(to_upload)} images to Horoshop...")
        try:
            tokens = get_tokens()
            print("  Auth OK")
        except Exception as exc:
            print(f"  Auth failed: {exc}")
            save_checkpoint(cp)
            return

        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = {
                pool.submit(horoshop_upload_one, art, path, tokens): art
                for art, path in to_upload.items()
            }
            for fut in as_completed(futures):
                art = futures[fut]
                try:
                    res = fut.result()
                except Exception as exc:
                    res = {"article": art, "status": "exception", "error": str(exc)}

                status = res.get("status")
                if status == "uploaded":
                    print(f"  OK  {art}")
                    done_articles[art] = True
                    stats["uploaded"] += 1
                else:
                    print(f"  ERR {art}: {status} — {res.get('error') or res.get('reason')}")
                    upload_failed.append(res)
                    stats["upload_fail"] += 1

        cp.update({"done": done_articles, "upload_failed": upload_failed,
                   "search_failed": search_failed})
        save_checkpoint(cp)

    elif args.dry_run and to_upload:
        print(f"\n[DRY-RUN] Would upload {len(to_upload)} images")

    # ── Report ────────────────────────────────────────────────────────────────
    report = {
        "stats": stats,
        "total_done_all_runs": len(done_articles),
        "search_failed_count": len(search_failed),
        "upload_failed_count": len(upload_failed),
        "upload_failed_sample": upload_failed[:20],
        "search_failed_sample": search_failed[:30],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")

    print("\n── Summary ──────────────────────────────────────────────────────────")
    for k, v in stats.items():
        if v:
            print(f"  {k}: {v}")
    print(f"  total done (all runs): {len(done_articles)}")
    print(f"  report saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()
