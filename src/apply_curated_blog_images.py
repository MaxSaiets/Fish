from __future__ import annotations

import json
import re
import sys
import time
from io import BytesIO
from pathlib import Path

import requests
import urllib3
from PIL import Image, ImageEnhance, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fill_horoshop_content_pages import load_env, parse_form_payload
from replace_blog_images_openverse import figure, replace_figures


urllib3.disable_warnings()

ROOT = Path(r"D:\FISH\fish-sync")
CANDIDATES = ROOT / "data" / "openverse_filtered_candidates_20260602.json"
OUT_DIR = ROOT / "public" / "blog-curated-images"
CHECKPOINT = ROOT / "data" / "blog_curated_images_checkpoint_20260602.json"
REPORT = ROOT / "data" / "blog_curated_images_report_20260602.json"


# First 20 numbers are ordered to fix the visible first rows of the blog.
CURATED_NUMBERS = [
    2, 165, 48, 50, 52, 26, 33, 88, 111, 20,
    7, 164, 53, 47, 54, 57, 94, 91, 21, 24,
    9, 10, 11, 1, 5, 8, 13, 14, 22, 46,
    51, 55, 56, 62, 64, 65, 67, 73, 89, 90,
    92, 93, 95, 97, 98, 99, 100, 101, 102, 103,
    104, 105, 108, 109, 110, 112, 114, 115, 118, 119,
    127, 130, 162, 167, 168, 169, 170, 171, 173, 174,
    175, 176, 182, 185, 187, 198, 201, 204, 208, 209,
    19, 4, 6, 17, 18, 58, 59, 60, 63, 78,
    81, 87, 107, 113, 124, 129,
]


def retry_get(session: requests.Session, url: str, **kwargs):
    for attempt in range(5):
        try:
            return session.get(url, **kwargs)
        except requests.RequestException:
            if attempt == 4:
                raise
            time.sleep(2 + attempt)


def retry_post(session: requests.Session, url: str, **kwargs):
    for attempt in range(5):
        try:
            return session.post(url, **kwargs)
        except requests.RequestException:
            if attempt == 4:
                raise
            time.sleep(2 + attempt)


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


def candidates_by_num() -> dict[int, dict]:
    items = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    return {int(item["num"]): item for item in items}


def prepare_image(session: requests.Session, item: dict, output: Path, index: int) -> Path:
    if output.exists():
        return output
    response = retry_get(session, item["url"], timeout=60)
    response.raise_for_status()
    image = Image.open(BytesIO(response.content)).convert("RGB")
    center = (0.5 + ((index % 5) - 2) * 0.03, 0.5 + ((index % 3) - 1) * 0.025)
    image = ImageOps.fit(image, (1200, 800), method=Image.Resampling.LANCZOS, centering=center)
    image = ImageEnhance.Color(image).enhance(1.05)
    image = ImageEnhance.Contrast(image).enhance(1.04)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "JPEG", quality=87, optimize=True, progressive=True)
    return output


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


def update_record(session: requests.Session, base_url: str, record: dict[str, str], preview_path: Path, first_url: str, second_url: str, checkpoint: dict) -> dict:
    key = f"{record['id']}:{preview_path.name}"
    if key in checkpoint["updated"]:
        return checkpoint["updated"][key]
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
    files = {"names[img][file]": (preview_path.name, preview_path.open("rb"), "image/jpeg")}
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
    result = {"id": record["id"], "title": record["title"], "preview": first_url, "body": second_url, "status": save.status_code}
    checkpoint["updated"][key] = result
    save_checkpoint(checkpoint)
    return result


def audit(session: requests.Session, base_url: str, records: list[dict[str, str]]) -> dict:
    preview_counts: dict[str, int] = {}
    body_counts: dict[str, int] = {}
    public_bad = []
    for record in records:
        edit_url = f"{base_url}/adminLegacy/edit.php?id={record['id']}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
        response = retry_get(session, edit_url, timeout=60, verify=False)
        payload = parse_form_payload(response.text)
        preview = payload.get("names[img][value]", "")
        preview_counts[preview] = preview_counts.get(preview, 0) + 1
        for src in re.findall(r'<img[^>]+src=["\']([^"\']+)', payload.get("names[i18n][3][text]", ""), flags=re.I):
            body_counts[src] = body_counts.get(src, 0) + 1
        public = retry_get(session, f"{base_url}/{record['slug'].strip('/')}/?curated_audit=1", timeout=60, verify=False)
        if public.status_code != 200 or record["title"] not in public.text:
            public_bad.append({"id": record["id"], "status": public.status_code})
    blog = retry_get(session, f"{base_url}/blog/?curated_audit=1", timeout=60, verify=False)
    return {
        "duplicate_previews": {url: count for url, count in preview_counts.items() if url and count > 1},
        "duplicate_body_images": {url: count for url, count in body_counts.items() if count > 1},
        "missing_previews": sum(1 for url in preview_counts if not url),
        "body_total": sum(body_counts.values()),
        "body_unique": len(body_counts),
        "public_bad": public_bad,
        "blog_noPhoto": blog.text.count("noPhoto"),
        "blog_camera": blog.text.count("camera"),
    }


def main() -> int:
    env = load_env()
    base_url = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-curated-blog-images/1.0"
    session.post(
        f"{base_url}/core-api/admin/security/login",
        json={"login": env["HOROSHOP_LOGIN"], "password": env["HOROSHOP_PASS"]},
        timeout=60,
        verify=False,
    ).raise_for_status()
    records = active_blog_records(session, base_url)
    needed = len(records) * 2
    if len(CURATED_NUMBERS) < needed:
        raise RuntimeError(f"Need {needed} curated numbers, have {len(CURATED_NUMBERS)}")
    by_num = candidates_by_num()
    checkpoint = load_checkpoint()
    prepared = []
    uploaded = []
    for index, number in enumerate(CURATED_NUMBERS[:needed]):
        item = by_num[number]
        path = prepare_image(session, item, OUT_DIR / f"curated_{index+1:03d}_{number:03d}.jpg", index)
        prepared.append({"number": number, "path": str(path), "source": item})
        uploaded.append(upload_image(session, base_url, path, checkpoint))
        time.sleep(0.08)
    updated = []
    for index, record in enumerate(records):
        updated.append(update_record(session, base_url, record, Path(prepared[index * 2]["path"]), uploaded[index * 2], uploaded[index * 2 + 1], checkpoint))
        time.sleep(0.15)
    audit_result = audit(session, base_url, records)
    report = {
        "active_count": len(records),
        "prepared_count": len(prepared),
        "updated_count": len(updated),
        "prepared": prepared,
        "updated": updated,
        **audit_result,
        "license_note": "Images selected from Openverse results with open licenses allowing commercial use and modification. Source URLs and licenses are stored per image in prepared[].",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "active_count": report["active_count"],
        "prepared_count": report["prepared_count"],
        "updated_count": report["updated_count"],
        "duplicate_previews": report["duplicate_previews"],
        "duplicate_body_images": report["duplicate_body_images"],
        "blog_noPhoto": report["blog_noPhoto"],
        "blog_camera": report["blog_camera"],
        "public_bad": report["public_bad"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
