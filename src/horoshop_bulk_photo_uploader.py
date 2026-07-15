"""
horoshop_bulk_photo_uploader.py

Масово завантажує оброблені фото товарів у Horoshop через правильний
check -> AWS upload -> assign flow.

КЛЮЧОВЕ ВІДКРИТТЯ (2026-06-01):
  assign endpoint потребує ПОВНИЙ об'єкт check-відповіді (awsKey, title,
  handler, parent, param, projectUuid, sortOrder) ЗЛИТИЙ з upload-item
  та оригінальним filename. Інакше -> "Data integrity violation".

  Правильний payload:
    {"images": [{**check_data, **upload_item, "filename": filename}],
     "cleanGallery": <bool>}

Запуск:
    python src/horoshop_bulk_photo_uploader.py --dry-run
    python src/horoshop_bulk_photo_uploader.py --clean-gallery --concurrency 4
    python src/horoshop_bulk_photo_uploader.py --limit 100
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

ROOT = Path(r"D:\FISH\fish-sync")
UTILITY_DIR = ROOT / "public" / "mass-photo-utility"
CHECKPOINT_PATH = ROOT / "data" / "horoshop_bulk_upload_checkpoint.json"
REPORT_PATH = ROOT / "data" / "horoshop_bulk_upload_report.json"
ENV_FILE = ROOT / ".env"

requests.packages.urllib3.disable_warnings()  # silence InsecureRequestWarning


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in ENV_FILE.read_text("utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def login_and_tokens(env: dict) -> tuple[requests.Session, str, dict]:
    base = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    sess = requests.Session()
    sess.headers["User-Agent"] = "Mozilla/5.0"
    r = sess.post(f"{base}/core-api/admin/security/login",
                  json={"login": env["HOROSHOP_LOGIN"], "password": env["HOROSHOP_PASS"]},
                  timeout=30, verify=False)
    if int(r.json().get("status") or 0) != 200:
        raise RuntimeError(f"login failed: {r.text[:200]}")
    r = sess.get(f"{base}/core-api/admin/jwt/project-jwt/import-metadata", timeout=30, verify=False)
    meta = r.json()["payload"]["metadata"]
    return sess, base, meta


def load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        try:
            return json.loads(CHECKPOINT_PATH.read_text("utf-8"))
        except Exception:
            pass
    return {"done": [], "failed": []}


_cp_lock = threading.Lock()


def save_checkpoint(cp: dict) -> None:
    with _cp_lock:
        CHECKPOINT_PATH.write_text(json.dumps(cp, ensure_ascii=False, indent=2), "utf-8")


def upload_one(sess: requests.Session, base: str, meta: dict,
               img_path: Path, clean_gallery: bool) -> dict:
    filename = img_path.name
    jwt = meta["project_jwt"]
    aws = meta["aws_endpoint"]
    cloud = meta["cloud_token"]
    auth_jwt = {"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"}

    # 1. check
    try:
        r = sess.post(f"{base}/api/import-images/check", headers=auth_jwt,
                      json={"images": [filename]}, timeout=30)
        check_data = r.json()["response"]["data"].get(filename, {})
    except Exception as e:
        return {"file": filename, "status": "check_error", "error": str(e)}
    if not check_data.get("success"):
        return {"file": filename, "status": "no_product",
                "reason": check_data.get("message", "?")}

    # 2. AWS upload
    try:
        with img_path.open("rb") as fh:
            r = sess.post(f"{aws}/upload_images/upload-image",
                          headers={"Authorization": f"Bearer {cloud}"},
                          data={"projectUuid": check_data.get("projectUuid", ""),
                                "awsKey": check_data.get("awsKey", "")},
                          files={"file": (filename, fh, "image/jpeg")}, timeout=90)
        item = r.json()["data"]["items"][0]
        if not item.get("isSuccess"):
            return {"file": filename, "status": "aws_failed", "detail": str(item)[:120]}
    except Exception as e:
        return {"file": filename, "status": "aws_error", "error": str(e)}

    # 3. assign — MERGED payload (the working format)
    merged = {**check_data, **item, "filename": filename}
    try:
        r = sess.post(f"{base}/api/import-images/assign", headers=auth_jwt,
                      json={"images": [merged], "cleanGallery": clean_gallery}, timeout=30)
        body = r.json()
    except Exception as e:
        return {"file": filename, "status": "assign_error", "error": str(e)}

    if body.get("status") == 200 or (isinstance(body.get("response"), dict)
                                     and body["response"].get("success")):
        return {"file": filename, "status": "uploaded"}
    return {"file": filename, "status": "assign_failed",
            "detail": str(body.get("response"))[:120]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--utility-root", default=str(UTILITY_DIR))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--clean-gallery", action="store_true", default=False)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reset-checkpoint", action="store_true")
    args = ap.parse_args()

    util_dir = Path(args.utility_root)
    all_files = sorted(util_dir.glob("*@gallery_common.jpg"))
    print(f"Utility images: {len(all_files)}")

    cp = {"done": [], "failed": []} if args.reset_checkpoint else load_checkpoint()
    done = set(cp.get("done", []))

    pending = [f for f in all_files if f.name not in done]
    if args.offset:
        pending = pending[args.offset:]
    if args.limit:
        pending = pending[:args.limit]
    print(f"Already done: {len(done)} | Pending this run: {len(pending)} | clean_gallery={args.clean_gallery}")

    if args.dry_run:
        print("[DRY-RUN] first 10 pending:")
        for f in pending[:10]:
            print(f"  {f.name}")
        return
    if not pending:
        print("Nothing to do.")
        return

    env = load_env()
    sess, base, meta = login_and_tokens(env)
    print("Auth OK")

    stats = {"uploaded": 0, "no_product": 0, "failed": 0}
    failed = cp.get("failed", [])
    counter = {"n": 0}
    clock = {"t": time.time()}

    def worker(fp: Path) -> dict:
        return upload_one(sess, base, meta, fp, args.clean_gallery)

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(worker, f): f for f in pending}
        for fut in as_completed(futures):
            res = fut.result()
            st = res["status"]
            counter["n"] += 1
            if st == "uploaded":
                stats["uploaded"] += 1
                cp.setdefault("done", []).append(res["file"])
            elif st == "no_product":
                stats["no_product"] += 1
            else:
                stats["failed"] += 1
                failed.append(res)

            # periodic checkpoint + progress
            if counter["n"] % 25 == 0:
                cp["failed"] = failed[-500:]
                save_checkpoint(cp)
                rate = counter["n"] / max(1e-9, time.time() - clock["t"])
                print(f"  [{counter['n']}/{len(pending)}] up={stats['uploaded']} "
                      f"nop={stats['no_product']} fail={stats['failed']} "
                      f"({rate:.1f}/s)")
                # refresh tokens every ~1500 to avoid JWT expiry
                if counter["n"] % 1500 == 0:
                    try:
                        _, _, meta2 = login_and_tokens(env)
                        meta.update(meta2)
                        print("  (tokens refreshed)")
                    except Exception as e:
                        print(f"  token refresh failed: {e}")

    cp["failed"] = failed[-1000:]
    save_checkpoint(cp)

    report = {
        "utility_root": str(util_dir),
        "clean_gallery": args.clean_gallery,
        "stats": stats,
        "total_done_all_runs": len(cp.get("done", [])),
        "failed_count": len(failed),
        "failed_sample": failed[-30:],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")

    print("\n=== Summary ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"  total done (all runs): {len(cp.get('done', []))}")
    print(f"  report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
