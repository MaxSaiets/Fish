from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests
from PIL import Image


ROOT = Path(r"D:\FISH\fish-sync")
ENV_FILE = ROOT / ".env"
OUT_DIR = ROOT / "public" / "site-assets"
REPORT = ROOT / "data" / "horoshop_site_assets_report.json"

SOURCE_FILES = {
    "logo": Path(r"C:\Users\sayet\Downloads\Telegram Desktop\лого все для рибалки.svg"),
    "carp_sets": Path(r"C:\Users\sayet\Downloads\Telegram Desktop\коропові набори.png"),
    "veteran_500": Path(r"C:\Users\sayet\Downloads\Telegram Desktop\Ветеранський спорт 500.jpg"),
    "veteran_1000": Path(r"C:\Users\sayet\Downloads\Telegram Desktop\Ветеранський спорт 1000.jpg"),
    "veteran_1500": Path(r"C:\Users\sayet\Downloads\Telegram Desktop\Ветеранський спорт 1500.jpg"),
    "veteran_2000": Path(r"C:\Users\sayet\Downloads\Telegram Desktop\Ветеранський спорт 2000.jpg"),
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


def optimize_jpeg(source: Path, target: Path, max_size: int = 1600) -> dict:
    image = Image.open(source).convert("RGB")
    image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "JPEG", quality=84, optimize=True, progressive=True)
    return {"source_size": Image.open(source).size, "output_size": image.size}


def prepare_assets() -> dict[str, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prepared = {"logo": OUT_DIR / "logo-vse-dlia-rybalky.svg"}
    prepared["logo"].write_text(SOURCE_FILES["logo"].read_text(encoding="utf-8"), encoding="utf-8")
    logo_tight = OUT_DIR / "logo-vse-dlia-rybalky-tight.png"
    if logo_tight.exists():
        prepared["logo_tight_png"] = logo_tight
    optimize_jpeg(SOURCE_FILES["carp_sets"], OUT_DIR / "carp_sets_hero.jpg", max_size=2200)
    prepared["carp_sets"] = OUT_DIR / "carp_sets_hero.jpg"
    for key in ("veteran_500", "veteran_1000", "veteran_1500", "veteran_2000"):
        optimize_jpeg(SOURCE_FILES[key], OUT_DIR / f"{key}.jpg")
        prepared[key] = OUT_DIR / f"{key}.jpg"
    return prepared


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
    if not uri:
        raise RuntimeError(f"Upload response does not contain uri for {path.name}: {data}")
    if uri.startswith("/content/"):
        uri = uri.replace("/content/", "/", 1)
    if uri.startswith("/"):
        uri = f"{base_url}{uri}"
    return {"local_path": str(path), "uri": uri, "response": item}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    env = load_env()
    base_url = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    login = env.get("HOROSHOP_LOGIN", "").strip()
    password = env.get("HOROSHOP_PASS", "").strip()
    if not login or not password:
        raise RuntimeError("HOROSHOP_LOGIN/HOROSHOP_PASS are missing in .env")

    prepared = prepare_assets()
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-site-assets/1.0"
    admin_login(session, base_url, login, password, args.timeout)
    uploads = {key: upload_asset(session, base_url, path, args.timeout) for key, path in prepared.items()}
    payload = {"base_url": base_url, "prepared": {key: str(path) for key, path in prepared.items()}, "uploads": uploads}
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"uploaded": list(uploads), "report": str(REPORT)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
