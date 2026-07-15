from __future__ import annotations

import json
import mimetypes
import re
from pathlib import Path

import requests


ROOT = Path(r"D:\FISH")
GENERATED_ROOT = ROOT / "fish-sync" / "public" / "generated-product-images"
METADATA_DUMP = ROOT / "metadata-dump.md"
MAP_CACHE = ROOT / "fish-sync" / "data" / "live_missing_article_map.json"
CHECK_URL = "https://vsedliarybalky.com.ua/api/import-images/check"
ASSIGN_URL = "https://vsedliarybalky.com.ua/api/import-images/assign"


def extract_tokens() -> dict[str, str]:
    text = METADATA_DUMP.read_text(encoding="utf-8").replace('\\"', '"')
    matches = {
        "aws_endpoint": re.search(r'"aws_endpoint":\s*"([^"]+)"', text),
        "project_jwt": re.search(r'"project_jwt":\s*"([^"]+)"', text),
        "cloud_token": re.search(r'"cloud_token":\s*"([^"]+)"', text),
    }
    if not all(matches.values()):
        raise RuntimeError("Could not parse metadata dump tokens")
    return {key: match.group(1) for key, match in matches.items()}


def article_to_generated_path(article: str) -> Path:
    normalized = article.replace("\\", "/")
    return GENERATED_ROOT.joinpath(*normalized.split("/")) / "1.jpg"


def discover_special_articles() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    payload = json.loads(MAP_CACHE.read_text(encoding="utf-8"))
    for item in payload.get("items", []):
        article = str(item.get("article") or "").strip()
        if not article:
            continue
        if "/" not in article and "\\" not in article:
            continue
        image_path = article_to_generated_path(article)
        if not image_path.exists():
            continue
        items.append({"article": article, "path": str(image_path)})
    return sorted(items, key=lambda item: item["article"])


def check_image(session: requests.Session, jwt: str, filename: str) -> dict:
    response = session.post(
        CHECK_URL,
        headers={"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"},
        json={"images": [filename]},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["response"]["data"][filename]


def upload_binary(
    session: requests.Session,
    aws_endpoint: str,
    cloud_token: str,
    local_path: Path,
    remote_filename: str,
    image_meta: dict,
) -> dict:
    mime_type = mimetypes.guess_type(remote_filename)[0] or "application/octet-stream"
    with local_path.open("rb") as fh:
        response = session.post(
            f"{aws_endpoint}/upload_images/upload-image",
            headers={"Authorization": f"Bearer {cloud_token}"},
            data={
                "projectUuid": image_meta.get("projectUuid") or "",
                "awsKey": image_meta.get("awsKey") or "",
            },
            files={"file": (remote_filename, fh, mime_type)},
            timeout=120,
        )
    response.raise_for_status()
    return response.json()["data"]["items"][0]


def assign_image(session: requests.Session, jwt: str, uploaded: dict, image_meta: dict) -> dict:
    payload = {
        "images": [
            {
                "handler": image_meta.get("handler") or "",
                "param": image_meta.get("param") or "",
                "parent": image_meta.get("parent") or "",
                "uri": uploaded["uri"],
                "width": uploaded["width"],
                "height": uploaded["height"],
                "fileSize": uploaded["fileSize"],
                "sortOrder": image_meta.get("sortOrder", 0) or 0,
            }
        ],
        "cleanGallery": False,
    }
    response = session.post(
        ASSIGN_URL,
        headers={"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["response"]


def main() -> int:
    tokens = extract_tokens()
    session = requests.Session()
    articles = discover_special_articles()
    report = {"articles_total": len(articles), "uploaded": [], "failed": []}

    for index, item in enumerate(articles, start=1):
        article = item["article"]
        local_path = Path(item["path"])
        remote_filename = f"{article}@gallery_common.jpg"
        try:
            image_meta = check_image(session, tokens["project_jwt"], remote_filename)
            if not image_meta.get("success"):
                report["failed"].append({"article": article, "reason": "check_failed", "response": image_meta})
                print(f"[{index}/{len(articles)}] check failed {article}")
                continue
            uploaded = upload_binary(
                session,
                tokens["aws_endpoint"],
                tokens["cloud_token"],
                local_path,
                remote_filename,
                image_meta,
            )
            assigned = assign_image(session, tokens["project_jwt"], uploaded, image_meta)
            report["uploaded"].append({"article": article, "assign_success": assigned.get("success")})
            print(f"[{index}/{len(articles)}] uploaded {article}")
        except Exception as exc:  # noqa: BLE001
            report["failed"].append({"article": article, "reason": str(exc)})
            print(f"[{index}/{len(articles)}] failed {article}: {exc}")

    report_path = ROOT / "fish-sync" / "data" / "horoshop_special_placeholder_upload_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print({"report": str(report_path), "uploaded": len(report["uploaded"]), "failed": len(report["failed"])})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
