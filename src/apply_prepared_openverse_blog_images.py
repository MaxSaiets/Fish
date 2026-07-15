from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests
import urllib3

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fill_horoshop_content_pages import load_env, parse_form_payload
from replace_blog_images_openverse import figure, replace_figures


urllib3.disable_warnings()

ROOT = Path(r"D:\FISH\fish-sync")
IMAGE_DIR = ROOT / "public" / "blog-openverse-images"
CHECKPOINT = ROOT / "data" / "blog_openverse_apply_checkpoint_20260602.json"
REPORT = ROOT / "data" / "blog_openverse_apply_report_20260602.json"


def retry_get(session: requests.Session, url: str, **kwargs):
    for attempt in range(6):
        try:
            return session.get(url, **kwargs)
        except requests.RequestException:
            if attempt == 5:
                raise
            time.sleep(3 + attempt)


def retry_post(session: requests.Session, url: str, **kwargs):
    for attempt in range(6):
        try:
            return session.post(url, **kwargs)
        except requests.RequestException:
            if attempt == 5:
                raise
            time.sleep(3 + attempt)


def load_checkpoint() -> dict:
    if CHECKPOINT.exists():
        return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    return {"uploads": {}, "updated": {}}


def save_checkpoint(data: dict) -> None:
    CHECKPOINT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def active_blog_records(session: requests.Session, base_url: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for record_id in range(1, 180):
        edit_url = f"{base_url}/adminLegacy/edit.php?id={record_id}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
        response = retry_get(session, edit_url, timeout=60, verify=False)
        if response.status_code != 200 or "h_news" not in response.text:
            continue
        payload = parse_form_payload(response.text)
        if payload.get("names[act]") != "1":
            continue
        title = payload.get("names[i18n][3][title]", "")
        slug = payload.get("names[name][slug]", "")
        if title and slug:
            records.append({"id": str(record_id), "title": title, "slug": slug})
    records.sort(key=lambda item: int(item["id"]))
    return records


def prepared_images(count: int) -> list[Path]:
    images = sorted(IMAGE_DIR.glob("blog_openverse_*.jpg"))
    images = [path for path in images if not path.name.endswith(".source.jpg")]
    if len(images) < count:
        raise RuntimeError(f"Need {count} prepared images, found {len(images)}")
    return images[:count]


def upload_image(session: requests.Session, base_url: str, path: Path, checkpoint: dict) -> str:
    key = str(path)
    if key in checkpoint["uploads"]:
        return checkpoint["uploads"][key]
    with path.open("rb") as fh:
        response = retry_post(
            session,
            f"{base_url}/core-api/admin/app-json/upload-image",
            files={"file": (path.name, fh, "image/jpeg")},
            timeout=120,
            verify=False,
        )
    response.raise_for_status()
    data = response.json()
    payload = data.get("payload")
    item = payload[0] if isinstance(payload, list) else payload
    uri = str(item.get("uri") or "")
    if uri.startswith("/content/"):
        uri = uri.replace("/content/", "/", 1)
    if uri.startswith("/"):
        uri = f"{base_url}{uri}"
    if not uri:
        raise RuntimeError(f"Upload response without uri for {path}: {data}")
    checkpoint["uploads"][key] = uri
    save_checkpoint(checkpoint)
    return uri


def update_record(
    session: requests.Session,
    base_url: str,
    record: dict[str, str],
    preview_file: Path,
    first_url: str,
    second_url: str,
    checkpoint: dict,
) -> dict:
    if record["id"] in checkpoint["updated"]:
        return checkpoint["updated"][record["id"]]
    edit_url = f"{base_url}/adminLegacy/edit.php?id={record['id']}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
    response = retry_get(session, edit_url, timeout=60, verify=False)
    response.raise_for_status()
    payload = parse_form_payload(response.text)
    body = payload.get("names[i18n][3][text]", "")
    body = replace_figures(body, first_url, second_url, record["title"])
    payload.update(
        {
            "checkcode": "yamete_kudasai",
            "id": record["id"],
            "handler": "172",
            "handlertable": "h_news",
            "back": "index.php",
            "names[act]": "1",
            "names[parent]": "1001",
            "names[i18n][3][text]": body,
        }
    )
    files = {"names[img][file]": (preview_file.name, preview_file.open("rb"), "image/jpeg")}
    try:
        save = retry_post(
            session,
            f"{base_url}/adminLegacy/save.php",
            data=payload,
            files=files,
            headers={"Referer": edit_url},
            timeout=120,
            verify=False,
            allow_redirects=True,
        )
    finally:
        files["names[img][file]"][1].close()
    save.raise_for_status()
    item = {
        "id": record["id"],
        "title": record["title"],
        "preview_file": str(preview_file),
        "first_url": first_url,
        "second_url": second_url,
        "status": save.status_code,
    }
    checkpoint["updated"][record["id"]] = item
    save_checkpoint(checkpoint)
    return item


def duplicate_audit(session: requests.Session, base_url: str, records: list[dict[str, str]]) -> dict:
    body_counts: dict[str, int] = {}
    preview_counts: dict[str, int] = {}
    missing_preview = 0
    public_bad = []
    for record in records:
        edit_url = f"{base_url}/adminLegacy/edit.php?id={record['id']}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
        response = retry_get(session, edit_url, timeout=60, verify=False)
        payload = parse_form_payload(response.text)
        preview = payload.get("names[img][value]", "")
        if not preview:
            missing_preview += 1
        preview_counts[preview] = preview_counts.get(preview, 0) + 1
        for src in re.findall(r'<img[^>]+src=["\']([^"\']+)', payload.get("names[i18n][3][text]", ""), flags=re.I):
            body_counts[src] = body_counts.get(src, 0) + 1
        public = retry_get(session, f"{base_url}/{record['slug'].strip('/')}/?openverse_apply_audit=1", timeout=60, verify=False)
        if public.status_code != 200 or record["title"] not in public.text:
            public_bad.append({"id": record["id"], "status": public.status_code})
    blog = retry_get(session, f"{base_url}/blog/?openverse_apply_audit=1", timeout=60, verify=False)
    return {
        "duplicate_previews": {url: count for url, count in preview_counts.items() if url and count > 1},
        "duplicate_body_images": {url: count for url, count in body_counts.items() if count > 1},
        "body_image_total": sum(body_counts.values()),
        "body_image_unique": len(body_counts),
        "missing_preview": missing_preview,
        "public_bad": public_bad,
        "blog_noPhoto": blog.text.count("noPhoto"),
        "blog_camera": blog.text.count("camera"),
    }


def main() -> int:
    env = load_env()
    base_url = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-openverse-apply/1.0"
    session.post(
        f"{base_url}/core-api/admin/security/login",
        json={"login": env["HOROSHOP_LOGIN"], "password": env["HOROSHOP_PASS"]},
        timeout=60,
        verify=False,
    ).raise_for_status()

    records = active_blog_records(session, base_url)
    images = prepared_images(len(records) * 2)
    checkpoint = load_checkpoint()
    uploaded = []
    for path in images:
        uploaded.append(upload_image(session, base_url, path, checkpoint))
        time.sleep(0.08)
    updated = []
    for index, record in enumerate(records):
        updated.append(
            update_record(
                session,
                base_url,
                record,
                images[index * 2],
                uploaded[index * 2],
                uploaded[index * 2 + 1],
                checkpoint,
            )
        )
        time.sleep(0.15)

    audit = duplicate_audit(session, base_url, records)
    report = {
        "active_count": len(records),
        "uploaded_count": len(uploaded),
        "updated_count": len(updated),
        "updated": updated,
        **audit,
        "source_policy": {
            "provider": "Openverse API",
            "license_filter": "cc0,pdm",
            "docs": "https://docs.openverse.org/api/",
        },
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "active_count": report["active_count"],
        "uploaded_count": report["uploaded_count"],
        "updated_count": report["updated_count"],
        "duplicate_previews": report["duplicate_previews"],
        "duplicate_body_images": report["duplicate_body_images"],
        "body_image_total": report["body_image_total"],
        "body_image_unique": report["body_image_unique"],
        "missing_preview": report["missing_preview"],
        "blog_noPhoto": report["blog_noPhoto"],
        "blog_camera": report["blog_camera"],
        "public_bad": report["public_bad"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
