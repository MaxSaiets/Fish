from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from pathlib import Path

import requests
import urllib3
from PIL import Image, ImageEnhance, ImageOps

from upload_horoshop_category_visuals import family_for_slug


urllib3.disable_warnings()

ROOT = Path(r"D:\FISH\fish-sync")
ENV_FILE = ROOT / ".env"
REPORT = ROOT / "data" / "horoshop_category_visuals_report.json"
INVENTORY = Path(r"F:\FISH_IMAGES\_extracted\_image_inventory.csv")
EXTRACTED_ROOT = Path(r"F:\FISH_IMAGES\_extracted")
OUT_DIR = ROOT / "public" / "site-category-assets-unique"


UK_SYNONYMS: dict[str, set[str]] = {
    "kherabuna": {"херабуна", "herabuna"},
    "vudylyshcha": {"вудилище", "вудилища", "вудка", "вудочка", "rod", "удилище"},
    "kotushky": {"котушка", "котушки", "reel"},
    "volosin": {"волосінь", "жилки", "жилка", "шнур", "шнури", "флюорокарбон", "line"},
    "hachky": {"гачок", "гачки", "hook", "двійник", "трійник", "офсет"},
    "montazh": {"монтаж", "оснастка", "повідок", "карабін", "вертлюг", "кільця"},
    "hruzyla": {"груз", "грузило", "грузила", "оливо"},
    "kormushky": {"годівниця", "кормушка", "кормушки", "method", "feeder"},
    "syhnalizatory": {"сигналізатор", "свінгер", "кивок"},
    "nasadochni": {"насадка", "бойл", "boil", "pop-up", "поп", "діп", "зерно"},
    "prykormka": {"прикормка", "прикорм", "fanatic", "anvi", "realfish", "інтеркріл", "макуха"},
    "peletsy": {"пелетс", "pellet", "pelets", "пелец"},
    "pva": {"pva", "пва"},
    "pidsak": {"підсак", "садок", "кукан"},
    "zymova": {"зима", "зимова", "льодобур", "мормишка", "жерлиця", "мотильниця"},
    "turyzm": {"туризм", "ліхтар", "термос", "плита", "пальник", "посуд"},
    "prymanky": {"приманка", "воблер", "блешня", "балансир", "мандула", "lure"},
    "chokhly": {"чохол", "чохли", "тубус", "сумка"},
    "vidra": {"відро", "відра", "коробка", "органайзер", "повідочниця"},
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
    repl = {
        "і": "i",
        "ї": "i",
        "є": "e",
        "ґ": "g",
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "h",
        "д": "d",
        "е": "e",
        "ж": "zh",
        "з": "z",
        "и": "y",
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
        "ю": "iu",
        "я": "ia",
        "ь": "",
        "'": "",
    }
    out = "".join(repl.get(ch, ch) for ch in text)
    return re.sub(r"[^a-z0-9]+", " ", out).strip()


def tokens(text: str) -> set[str]:
    return {t for t in normalize(text).split() if len(t) > 2}


def expand_slug_tokens(slug: str) -> set[str]:
    base = tokens(slug)
    expanded = set(base)
    for token in list(base):
        for key, values in UK_SYNONYMS.items():
            if token in key or key in token:
                expanded |= tokens(" ".join(values))
    return expanded


def load_inventory() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with INVENTORY.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("is_image") == "True" and not row.get("issues"):
                row["abs_path"] = str(EXTRACTED_ROOT / row["relative_path"])
                row["token_text"] = " ".join([row.get("archive", ""), row.get("relative_path", ""), row.get("file_name", "")])
                rows.append(row)
    return rows


def choose_images(category_map: dict[str, str], inventory: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    used: set[str] = set()
    choices: dict[str, dict[str, str]] = {}
    scored_cache = [(row, tokens(row["token_text"])) for row in inventory]
    for slug in sorted(category_map):
        wanted = expand_slug_tokens(slug)
        best: tuple[float, dict[str, str] | None] = (-1, None)
        for row, row_tokens in scored_cache:
            if row["sha256"] in used:
                continue
            overlap = len(wanted & row_tokens)
            archive_bonus = len(tokens(row.get("archive", "")) & wanted) * 1.8
            name_bonus = len(tokens(row.get("file_name", "")) & wanted) * 2.2
            size_bonus = min(float(row.get("megapixels") or 0), 2.0) * 0.2
            score = overlap + archive_bonus + name_bonus + size_bonus
            if score > best[0]:
                best = (score, row)
        row = best[1]
        if row and best[0] >= 5.0:
            used.add(row["sha256"])
            choices[slug] = {"source_type": "archive", "score": f"{best[0]:.2f}", **row}
    return choices


def unique_crop_anchor(slug: str) -> tuple[float, float]:
    digest = hashlib.sha256(slug.encode("utf-8")).digest()
    x = 0.42 + (digest[0] / 255) * 0.16
    y = 0.42 + (digest[1] / 255) * 0.16
    return (x, y)


def prepare_image(source: Path, target: Path, slug: str) -> None:
    image = Image.open(source).convert("RGB")
    image = ImageOps.fit(image, (1200, 840), method=Image.Resampling.LANCZOS, centering=unique_crop_anchor(slug))
    digest = hashlib.sha256(slug.encode("utf-8")).digest()
    image = ImageEnhance.Color(image).enhance(1.02 + (digest[2] / 255) * 0.06)
    image = ImageEnhance.Contrast(image).enhance(1.03 + (digest[3] / 255) * 0.05)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "JPEG", quality=84, optimize=True, progressive=True)


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


def key_for_slug(slug: str) -> str:
    return "cat_" + re.sub(r"[^a-z0-9]+", "_", slug.strip("/").lower()).strip("_")


def main() -> int:
    env = load_env()
    base_url = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    login = env.get("HOROSHOP_LOGIN", "").strip()
    password = env.get("HOROSHOP_PASS", "").strip()
    if not login or not password:
        raise RuntimeError("HOROSHOP_LOGIN/HOROSHOP_PASS are missing in .env")

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    existing_category_map = report.get("category_map") or {}
    category_map = {slug: family_for_slug(slug) for slug in existing_category_map}
    inventory = load_inventory()
    choices = choose_images(category_map, inventory)

    prepared: dict[str, dict[str, str]] = {}
    for slug, info in choices.items():
        key = key_for_slug(slug)
        target = OUT_DIR / f"{key}.jpg"
        prepare_image(Path(info["abs_path"]), target, slug)
        prepared[key] = {
            "slug": slug,
            "source_type": info["source_type"],
            "score": info["score"],
            "source": info["abs_path"],
            "local_path": str(target),
        }

    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-unique-category-previews/1.0"
    admin_login(session, base_url, login, password, 180)
    uploads = report.setdefault("uploads", {})
    new_category_map = dict(category_map)
    for key, info in prepared.items():
        uploads[key] = upload_asset(session, base_url, Path(info["local_path"]), 180)
        new_category_map[info["slug"]] = key

    report["category_map"] = new_category_map
    report["unique_archive_previews"] = {
        "prepared_count": len(prepared),
        "coverage_count": len(set(info["slug"] for info in prepared.values())),
        "coverage_percent": round(len(prepared) / max(len(category_map), 1) * 100, 2),
        "prepared": prepared,
        "not_matched": sorted(set(category_map) - set(info["slug"] for info in prepared.values())),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["unique_archive_previews"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
