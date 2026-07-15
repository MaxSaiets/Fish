from __future__ import annotations

import json
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import requests
import urllib3

urllib3.disable_warnings()

ROOT = Path(r"D:\FISH\fish-sync")
ENV_FILE = ROOT / ".env"


UPDATES = [
    {"id": "1098", "parent": "1239", "title": "Годівниці", "inmenu": True},
    {"id": "1102", "parent": "1239", "title": "Інше для оснащення", "inmenu": True},
    {"id": "1115", "parent": "1247", "title": "Інструменти", "inmenu": True},
    {"id": "1202", "parent": "1235", "title": "Запчастини та аксесуари для вудок", "inmenu": True},
    {"id": "1256", "parent": "1099", "title": "Звичайні гачки", "inmenu": False},
    {"id": "1166", "parent": "1108", "title": "Fanatik", "inmenu": True},
    {"id": "1267", "parent": "1108", "title": "Anvi", "inmenu": True},
    {"id": "1268", "parent": "1108", "title": "Real Fish", "inmenu": True},
    {"id": "1216", "parent": "1108", "title": "Interkril", "inmenu": True},
    {"id": "1271", "parent": "1110", "title": "Bounty", "inmenu": True},
    {"id": "1272", "parent": "1110", "title": "Anvi", "inmenu": True},
    {"id": "1273", "parent": "1110", "title": "Fanatik", "inmenu": True},
    {"id": "1274", "parent": "1110", "title": "Boom", "inmenu": True},
    {"id": "1275", "parent": "1110", "title": "RPF", "inmenu": True},
    {"id": "1276", "parent": "1110", "title": "Puhach", "inmenu": True},
]


class LegacyFormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.fields: dict[str, str] = {}
        self._textarea_name: str | None = None
        self._textarea_chunks: list[str] = []
        self._select_name: str | None = None
        self._select_value: str | None = None

    def handle_starttag(self, tag: str, attrs_raw: list[tuple[str, str | None]]) -> None:
        attrs = {key: value or "" for key, value in attrs_raw}
        if tag == "input":
            name = attrs.get("name")
            if not name:
                return
            input_type = attrs.get("type", "text").lower()
            if input_type == "file":
                return
            if input_type in {"checkbox", "radio"} and "checked" not in attrs:
                return
            self.fields[name] = attrs.get("value", "")
        elif tag == "textarea":
            name = attrs.get("name")
            if name:
                self._textarea_name = name
                self._textarea_chunks = []
        elif tag == "select":
            self._select_name = attrs.get("name") or None
            self._select_value = None
        elif tag == "option":
            if not self._select_name or "selected" not in attrs:
                return
            self._select_value = attrs.get("value", "")

    def handle_data(self, data: str) -> None:
        if self._textarea_name:
            self._textarea_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "textarea" and self._textarea_name:
            self.fields[self._textarea_name] = "".join(self._textarea_chunks)
            self._textarea_name = None
            self._textarea_chunks = []
        elif tag == "select" and self._select_name:
            self.fields[self._select_name] = self._select_value or ""
            self._select_name = None
            self._select_value = None


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def get_base_url(env: dict[str, str]) -> str:
    explicit = env.get("HOROSHOP_BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    return "http://shop647643.horoshop.ua"


def auth(session: requests.Session, base_url: str, login: str, password: str) -> None:
    response = session.post(
        f"{base_url}/core-api/admin/security/login",
        json={"login": login, "password": password},
        headers={"Content-Type": "application/json"},
        timeout=30,
        verify=False,
    )
    response.raise_for_status()
    session.get(f"{base_url}/adminLegacy/", timeout=30, verify=False)


def build_seo(title: str) -> dict[str, str]:
    title_l = title.lower()
    return {
        "seo_title": f"{title} — купити рибальські товари онлайн",
        "seo_description": f"Купити {title_l} в інтернет-магазині рибальських товарів. Широкий вибір, низькі ціни, швидка доставка по Україні.",
        "seo_keywords": f"{title_l}, рибальські товари, купити",
        "h1_title": title,
    }


def post_form(session: requests.Session, url: str, payload: dict[str, Any], referer: str) -> requests.Response:
    response = session.post(
        url,
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": referer,
        },
        timeout=30,
        verify=False,
        allow_redirects=True,
    )
    response.raise_for_status()
    return response


def fetch_slug(session: requests.Session, base_url: str, section_id: str, title: str) -> tuple[str, str]:
    payload = {
        "fields[title]": title,
        "param_id": "1",
        "record_id": section_id,
        "parent_id": "97",
    }
    response = post_form(
        session,
        f"{base_url}/_widget/zteel_params_url_Param/updateUriAutomatically",
        payload,
        f"{base_url}/adminLegacy/",
    )
    data = response.json()
    if data.get("status") != "OK":
        raise RuntimeError(f"Slug widget failed for section {section_id}: {json.dumps(data, ensure_ascii=False)}")
    slug = str((data.get("response") or {}).get("slug") or "").strip()
    url_parent = str((data.get("response") or {}).get("parent") or "").strip()
    if not slug:
        raise RuntimeError(f"Empty slug for section {section_id}")
    return slug, url_parent


def fetch_full_form_payload(
    session: requests.Session,
    base_url: str,
    section_id: str,
    parent_id: str,
) -> dict[str, str]:
    edit_url = (
        f"{base_url}/adminLegacy/edit.php?"
        f"id={urllib.parse.quote(section_id)}&parent={urllib.parse.quote(parent_id)}"
        "&handler=4&checkcode=yamete_kudasai&showPages"
    )
    response = session.get(edit_url, timeout=30, verify=False)
    response.raise_for_status()
    parser = LegacyFormParser()
    parser.feed(response.text)
    if "names[i18n][3][title]" not in parser.fields and "names[i18n][1][title]" not in parser.fields:
        raise RuntimeError(f"Could not parse editable title fields for section {section_id}")
    return dict(parser.fields)


def save_section(
    session: requests.Session,
    base_url: str,
    section_id: str,
    parent_id: str,
    title: str,
    inmenu: bool,
) -> str:
    slug, url_parent = fetch_slug(session, base_url, section_id, title)
    seo = build_seo(title)
    payload = fetch_full_form_payload(session, base_url, section_id, parent_id)
    payload.update({
        "checkcode": "yamete_kudasai",
        "id": section_id,
        "handler": "4",
        "handlertable": "pages",
        "back": "index.php",
        "names[parent]": parent_id,
        "names[id_parent]": parent_id,
        "names[name][slug]": slug,
        "names[name][parent]": url_parent,
        "names[name][forceUpdate]": "1",
        "names[i18n][3][title]": title,
        "names[i18n][1][title]": title,
        "names[i18n][3][seo_title]": seo["seo_title"],
        "names[i18n][3][seo_description]": seo["seo_description"],
        "names[i18n][3][seo_keywords]": seo["seo_keywords"],
        "names[i18n][3][h1_title]": seo["h1_title"],
        "names[inmenu]": "1" if inmenu else "0",
        "names[insitemap]": "1" if inmenu else "0",
        "names[noindex]": "0" if inmenu else "1",
        "names[nofollow]": "0" if inmenu else "1",
    })
    response = post_form(
        session,
        f"{base_url}/adminLegacy/save.php",
        payload,
        f"{base_url}/adminLegacy/edit.php?id={urllib.parse.quote(section_id)}&parent={urllib.parse.quote(parent_id)}&handler=4",
    )
    return response.url


def main() -> None:
    env = load_env()
    login = env.get("HOROSHOP_LOGIN", "").strip()
    password = env.get("HOROSHOP_PASS", "").strip()
    if not login or not password:
        raise RuntimeError("HOROSHOP_LOGIN/HOROSHOP_PASS are not configured")

    base_url = get_base_url(env)
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-menu-fixes/1.0"
    auth(session, base_url, login, password)

    results: list[dict[str, str]] = []
    for update in UPDATES:
        final_url = save_section(
            session,
            base_url,
            section_id=update["id"],
            parent_id=update["parent"],
            title=update["title"],
            inmenu=bool(update["inmenu"]),
        )
        results.append(
            {
                "id": update["id"],
                "title": update["title"],
                "inmenu": str(update["inmenu"]),
                "final_url": final_url,
            }
        )

    print(json.dumps({"base_url": base_url, "updated": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
