from __future__ import annotations

import argparse
import json
import mimetypes
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests


ROOT = Path(r"D:\FISH\fish-sync")
UTILITY_ROOT = ROOT / "public" / "horoshop-image-utility"
ENV_FILE = ROOT / ".env"
DEFAULT_METADATA_DUMP = Path(r"D:\FISH\metadata-dump.md")
DEFAULT_REPORT = ROOT / "data" / "horoshop_image_upload_report.json"
DEFAULT_VALID_ARTICLES_XML = ROOT / "public" / "horoshop.xml"
BASE_URL = "https://vsedliarybalky.com.ua"
CHECK_URL = "https://vsedliarybalky.com.ua/api/import-images/check"
ASSIGN_URL = "https://vsedliarybalky.com.ua/api/import-images/assign"
MAX_RETRIES = 4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--utility-root", default=str(UTILITY_ROOT))
    parser.add_argument("--metadata-dump", default=str(DEFAULT_METADATA_DUMP))
    parser.add_argument("--base-url", default="")
    parser.add_argument("--login", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--limit-articles", type=int, default=0)
    parser.add_argument("--offset-articles", type=int, default=0)
    parser.add_argument("--clean-gallery", action="store_true", default=False)
    parser.add_argument("--valid-articles-xml", default=str(DEFAULT_VALID_ARTICLES_XML))
    parser.add_argument("--allow-unmatched-articles", action="store_true", default=False)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--concurrency", type=int, default=1)
    return parser.parse_args()


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


def extract_tokens(metadata_dump: Path) -> dict[str, str]:
    text = metadata_dump.read_text(encoding="utf-8").replace('\\"', '"')
    matches = {
        "aws_endpoint": re.search(r'"aws_endpoint":\s*"([^"]+)"', text),
        "project_jwt": re.search(r'"project_jwt":\s*"([^"]+)"', text),
        "cloud_token": re.search(r'"cloud_token":\s*"([^"]+)"', text),
    }
    if not all(matches.values()):
        raise RuntimeError(f"Could not parse metadata tokens from {metadata_dump}")
    return {
        "aws_endpoint": matches["aws_endpoint"].group(1),
        "project_jwt": matches["project_jwt"].group(1),
        "cloud_token": matches["cloud_token"].group(1),
    }


def admin_login(
    session: requests.Session,
    base_url: str,
    login: str,
    password: str,
    timeout: int,
) -> None:
    response = session.post(
        f"{base_url}/core-api/admin/security/login",
        json={"login": login, "password": password},
        timeout=timeout,
        verify=False,
    )
    response.raise_for_status()
    data = response.json()
    if int(data.get("status") or 0) != 200:
        raise RuntimeError(f"Horoshop admin auth failed: {data}")


def fetch_import_metadata(session: requests.Session, base_url: str, timeout: int) -> dict[str, str]:
    response = session.get(
        f"{base_url}/core-api/admin/jwt/project-jwt/import-metadata",
        timeout=timeout,
        verify=False,
    )
    response.raise_for_status()
    data = response.json()
    metadata = ((data.get("payload") or {}).get("metadata") or {}) if isinstance(data, dict) else {}
    required = ("aws_endpoint", "project_jwt", "cloud_token")
    missing = [key for key in required if not metadata.get(key)]
    if missing:
        raise RuntimeError(f"Horoshop import metadata missing fields: {missing}")
    return {key: str(metadata[key]) for key in required}


def resolve_tokens(args: argparse.Namespace, session: requests.Session) -> tuple[dict[str, str], str]:
    env = load_env()
    base_url = (args.base_url or env.get("HOROSHOP_BASE_URL") or BASE_URL).strip().rstrip("/")
    login = (args.login or env.get("HOROSHOP_LOGIN") or "").strip()
    password = (args.password or env.get("HOROSHOP_PASS") or "").strip()
    if login and password:
        admin_login(session, base_url, login, password, args.timeout)
        return fetch_import_metadata(session, base_url, args.timeout), "admin-import-metadata"
    return extract_tokens(Path(args.metadata_dump)), "metadata-dump"


def sort_key(path: Path) -> tuple[int, int, str]:
    stem_parts = path.stem.split("@")
    order = 1
    if len(stem_parts) >= 3 and stem_parts[-1].isdigit():
        order = int(stem_parts[-1])
    return (0 if order == 1 else 1, order, path.name.lower())


def group_files_by_article(utility_root: Path) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path in utility_root.rglob("*"):
        if not path.is_file():
            continue
        article = path.stem.split("@")[0].strip()
        if not article:
            continue
        grouped[article].append(path)
    for article in grouped:
        grouped[article] = sorted(grouped[article], key=sort_key)
    return dict(sorted(grouped.items()))


def load_valid_articles(xml_path: Path) -> set[str]:
    if not xml_path.exists():
        raise FileNotFoundError(f"Valid articles XML not found: {xml_path}")
    root = ET.parse(xml_path).getroot()
    return {
        str(offer.attrib.get("id") or "").strip()
        for offer in root.findall(".//offer")
        if str(offer.attrib.get("id") or "").strip()
    }


def check_images(session: requests.Session, project_jwt: str, filenames: list[str], timeout: int) -> dict:
    response = session.post(
        CHECK_URL,
        headers={
            "Authorization": f"Bearer {project_jwt}",
            "Content-Type": "application/json",
        },
        json={"images": filenames},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()["response"]


def upload_image(
    session: requests.Session,
    aws_endpoint: str,
    cloud_token: str,
    file_path: Path,
    image_meta: dict,
    timeout: int,
) -> dict:
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    with file_path.open("rb") as fh:
        response = session.post(
            f"{aws_endpoint}/upload_images/upload-image",
            headers={"Authorization": f"Bearer {cloud_token}"},
            data={
                "projectUuid": image_meta.get("projectUuid") or "",
                "awsKey": image_meta.get("awsKey") or "",
            },
            files={"file": (file_path.name, fh, mime_type)},
            timeout=timeout,
        )
    response.raise_for_status()
    return response.json()["data"]["items"][0]


def assign_images(
    session: requests.Session,
    project_jwt: str,
    images: list[dict],
    clean_gallery: bool,
    timeout: int,
) -> dict:
    response = session.post(
        ASSIGN_URL,
        headers={
            "Authorization": f"Bearer {project_jwt}",
            "Content-Type": "application/json",
        },
        json={"images": images, "cleanGallery": clean_gallery},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()["response"]


def with_retry(fn, *args, **kwargs):
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt == MAX_RETRIES:
                break
            time.sleep(min(2 * attempt, 8))
    raise last_exc


def process_article(
    article: str,
    files: list[Path],
    tokens: dict[str, str],
    timeout: int,
    dry_run: bool,
    clean_gallery: bool,
) -> dict:
    session = requests.Session()
    filenames = [path.name for path in files]
    article_result = {
        "article": article,
        "file_count": len(files),
        "filenames": filenames,
    }
    checked = with_retry(check_images, session, tokens["project_jwt"], filenames, timeout)
    data_map = checked["data"]
    failed = {
        name: data
        for name, data in data_map.items()
        if not data.get("success")
    }
    if failed:
        article_result["status"] = "failed"
        article_result["reason"] = "check_failed"
        article_result["failed_checks"] = failed
        return article_result

    if dry_run:
        article_result["status"] = "validated"
        return article_result

    assign_payload: list[dict] = []
    for sort_order, path in enumerate(files):
        image_meta = data_map[path.name]
        uploaded = with_retry(
            upload_image,
            session,
            tokens["aws_endpoint"],
            tokens["cloud_token"],
            path,
            image_meta,
            timeout,
        )
        assign_payload.append(
            {
                "handler": image_meta.get("handler") or "",
                "param": image_meta.get("param") or "",
                "parent": image_meta.get("parent") or "",
                "uri": uploaded["uri"],
                "width": uploaded["width"],
                "height": uploaded["height"],
                "fileSize": uploaded["fileSize"],
                "sortOrder": image_meta.get("sortOrder", sort_order) or sort_order,
            }
        )

    assigned = with_retry(
        assign_images,
        session,
        tokens["project_jwt"],
        assign_payload,
        clean_gallery,
        timeout,
    )
    article_result["status"] = "uploaded"
    article_result["assign_success"] = assigned.get("success")
    return article_result


def main() -> int:
    args = parse_args()
    utility_root = Path(args.utility_root)
    report_path = Path(args.report)

    auth_session = requests.Session()
    auth_session.headers["User-Agent"] = "fish-sync-image-upload/1.0"
    tokens, token_source = resolve_tokens(args, auth_session)
    grouped = group_files_by_article(utility_root)
    skipped_unmatched_articles: list[dict] = []
    if args.valid_articles_xml and not args.allow_unmatched_articles:
        valid_articles = load_valid_articles(Path(args.valid_articles_xml))
        filtered_grouped: dict[str, list[Path]] = {}
        for article, files in grouped.items():
            if article in valid_articles:
                filtered_grouped[article] = files
                continue
            skipped_unmatched_articles.append(
                {
                    "article": article,
                    "file_count": len(files),
                    "filenames": [path.name for path in files],
                }
            )
        grouped = filtered_grouped
    articles = list(grouped.items())
    if args.offset_articles:
        articles = articles[args.offset_articles :]
    if args.limit_articles:
        articles = articles[: args.limit_articles]

    report = {
        "utility_root": str(utility_root),
        "token_source": token_source,
        "articles_total": len(articles),
        "clean_gallery": args.clean_gallery,
        "dry_run": args.dry_run,
        "valid_articles_xml": "" if args.allow_unmatched_articles else args.valid_articles_xml,
        "skipped_unmatched_articles": skipped_unmatched_articles,
        "uploaded_articles": [],
        "failed_articles": [],
    }

    if args.concurrency <= 1:
        for index, (article, files) in enumerate(articles, start=1):
            try:
                article_result = process_article(
                    article,
                    files,
                    tokens,
                    args.timeout,
                    args.dry_run,
                    args.clean_gallery,
                )
                if article_result.get("status") in {"uploaded", "validated"}:
                    report["uploaded_articles"].append(article_result)
                    print(f"[{index}/{len(articles)}] uploaded article {article} with {len(files)} files")
                else:
                    report["failed_articles"].append(article_result)
                    print(f"[{index}/{len(articles)}] failed article {article}: {article_result.get('reason')}", file=sys.stderr)
            except Exception as exc:  # noqa: BLE001
                report["failed_articles"].append(
                    {
                        "article": article,
                        "file_count": len(files),
                        "filenames": [path.name for path in files],
                        "reason": "exception",
                        "error": str(exc),
                    }
                )
                print(f"[{index}/{len(articles)}] failed article {article}: {exc}", file=sys.stderr)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        future_map = {}
        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            for index, (article, files) in enumerate(articles, start=1):
                future = executor.submit(
                    process_article,
                    article,
                    files,
                    tokens,
                    args.timeout,
                    args.dry_run,
                    args.clean_gallery,
                )
                future_map[future] = (index, article, files)

            for future in as_completed(future_map):
                index, article, files = future_map[future]
                try:
                    article_result = future.result()
                    if article_result.get("status") in {"uploaded", "validated"}:
                        report["uploaded_articles"].append(article_result)
                        print(f"[{index}/{len(articles)}] uploaded article {article} with {len(files)} files")
                    else:
                        report["failed_articles"].append(article_result)
                        print(f"[{index}/{len(articles)}] failed article {article}: {article_result.get('reason')}", file=sys.stderr)
                except Exception as exc:  # noqa: BLE001
                    report["failed_articles"].append(
                        {
                            "article": article,
                            "file_count": len(files),
                            "filenames": [path.name for path in files],
                            "reason": "exception",
                            "error": str(exc),
                        }
                    )
                    print(f"[{index}/{len(articles)}] failed article {article}: {exc}", file=sys.stderr)
                report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(
        {
            "articles_total": report["articles_total"],
            "uploaded_articles": len(report["uploaded_articles"]),
            "failed_articles": len(report["failed_articles"]),
            "report": str(report_path),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
