from __future__ import annotations

import argparse
import re
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
DEFAULT_CSS = Path(r"D:\FISH\brand_override_live.css")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--css", default=str(DEFAULT_CSS))
    parser.add_argument("--base-url", default="")
    parser.add_argument("--login", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--timeout", type=int, default=60)
    return parser.parse_args()


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if not ENV_FILE.exists():
        return env
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def resolve_settings(args: argparse.Namespace) -> tuple[str, str, str, Path]:
    env = load_env()
    base_url = (args.base_url or env.get("HOROSHOP_BASE_URL") or "").strip().rstrip("/")
    login = (args.login or env.get("HOROSHOP_LOGIN") or "").strip()
    password = (args.password or env.get("HOROSHOP_PASS") or "").strip()
    css_path = Path(args.css)
    if not base_url or not login or not password:
        raise RuntimeError("HOROSHOP_BASE_URL / HOROSHOP_LOGIN / HOROSHOP_PASS must be configured")
    if not css_path.exists():
        raise RuntimeError(f"CSS file not found: {css_path}")
    return base_url, login, password, css_path


def auth(session: requests.Session, base_url: str, login: str, password: str, timeout: int) -> None:
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


def fetch_legacy_page(session: requests.Session, base_url: str, timeout: int) -> str:
    response = session.get(
        f"{base_url}/adminLegacy/utils/edit-client-styles.php",
        timeout=timeout,
        verify=False,
    )
    response.raise_for_status()
    return response.text


def extract_csrf_token(html: str) -> str:
    match = re.search(r"GLOBAL_CSRF_TOKEN:\s*'([^']+)'", html)
    if not match:
        raise RuntimeError("Could not extract GLOBAL_CSRF_TOKEN from adminLegacy CSS editor page")
    return match.group(1)


def save_styles(
    session: requests.Session,
    base_url: str,
    csrf_token: str,
    desktop_css: str,
    timeout: int,
) -> dict:
    response = session.post(
        f"{base_url}/adminLegacy/js/lookup.php",
        headers={"X-CSRF-Token": csrf_token},
        data={
            "load": "saveStyles",
            "type": "client",
            "content[desktop]": desktop_css,
            "content[mobile]": "",
        },
        timeout=timeout,
        verify=False,
    )
    response.raise_for_status()
    return response.json()


def generate_css(session: requests.Session, base_url: str, csrf_token: str, timeout: int) -> dict:
    response = session.post(
        f"{base_url}/out/utils/scss/",
        headers={"X-CSRF-Token": csrf_token},
        data="clients",
        timeout=timeout,
        verify=False,
    )
    response.raise_for_status()
    try:
        return response.json()
    except Exception:
        return {
            "status": "RAW",
            "response": response.text[:1000],
        }


def main() -> int:
    args = parse_args()
    base_url, login, password, css_path = resolve_settings(args)
    desktop_css = css_path.read_text(encoding="utf-8")

    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-client-css/1.0"

    auth(session, base_url, login, password, args.timeout)
    html = fetch_legacy_page(session, base_url, args.timeout)
    csrf_token = extract_csrf_token(html)
    save_result = save_styles(session, base_url, csrf_token, desktop_css, args.timeout)
    generate_result = generate_css(session, base_url, csrf_token, args.timeout)

    print(
        {
            "base_url": base_url,
            "css_path": str(css_path),
            "css_length": len(desktop_css),
            "save_status": save_result.get("status"),
            "save_response": save_result.get("response"),
            "generate_status": generate_result.get("status"),
            "generate_response": generate_result.get("response"),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
