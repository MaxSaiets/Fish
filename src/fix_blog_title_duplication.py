# -*- coding: utf-8 -*-
"""
Безпечний точковий фікс: у 48 старих статей блогу перше речення тіла
буквально повторює заголовок статті ("<h1>ЗАГОЛОВОК</h1> ... <p><strong>
ЗАГОЛОВОК це тема, яка напряму впливає...") - видиме дублювання на
живій сторінці (title з'являється 2 рази поспіль). Прибирає лише цей
зайвий повтор заголовка з початку першого абзацу, НЕ чіпаючи інший текст
(шаблонність самого тексту - окреме, більше рішення).

  python src/fix_blog_title_duplication.py --dry-run
  python src/fix_blog_title_duplication.py
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import requests
import urllib3

from fill_horoshop_content_pages import load_env, parse_form_payload
from replace_blog_images_openverse import retry_get, retry_post

urllib3.disable_warnings()

REPORT = ROOT / "data" / "blog_title_dup_fix_20260713.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    env = load_env()
    base_url = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-blog-title-fix/1.0"
    session.post(
        f"{base_url}/core-api/admin/security/login",
        json={"login": env["HOROSHOP_LOGIN"], "password": env["HOROSHOP_PASS"]},
        timeout=60,
        verify=False,
    ).raise_for_status()

    records = json.load(open(ROOT / "data" / "blog_quality_audit_20260713.json", encoding="utf-8"))
    targets = [r for r in records if r["boilerplate"] and r["title_tripled"]]
    print(f"статей для фіксу: {len(targets)}", flush=True)

    results = []
    for rec in targets:
        record_id = rec["id"]
        title = rec["title"]
        edit_url = f"{base_url}/adminLegacy/edit.php?id={record_id}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
        response = retry_get(session, edit_url, timeout=60, verify=False)
        response.raise_for_status()
        payload = parse_form_payload(response.text)
        body = payload.get("names[i18n][3][text]", "")

        escaped_title = re.escape(title)
        pattern = re.compile(rf"(<p><strong>)\s*{escaped_title}\s+(це тема)", flags=re.I)
        new_body, n = pattern.subn(r"\1\2", body, count=1)
        if n == 0:
            results.append({"id": record_id, "title": title, "changed": False, "reason": "pattern_not_found"})
            print(f"  [SKIP] id={record_id}: патерн не знайдено :: {title}", flush=True)
            continue

        if args.dry_run:
            results.append({"id": record_id, "title": title, "changed": "dry_run"})
            print(f"  [DRY] id={record_id}: буде виправлено :: {title}", flush=True)
            continue

        payload.update(
            {
                "checkcode": "yamete_kudasai",
                "id": record_id,
                "handler": "172",
                "handlertable": "h_news",
                "back": "index.php",
                "names[act]": "1",
                "names[parent]": "1001",
                "names[i18n][3][text]": new_body,
            }
        )
        save = retry_post(
            session,
            f"{base_url}/adminLegacy/save.php",
            data=payload,
            headers={"Referer": edit_url},
            timeout=120,
            verify=False,
            allow_redirects=True,
        )
        save.raise_for_status()
        results.append({"id": record_id, "title": title, "changed": True, "status": save.status_code})
        print(f"  [OK] id={record_id} status={save.status_code} :: {title}", flush=True)

    REPORT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    changed = sum(1 for r in results if r.get("changed") is True)
    print(f"\nГОТОВО: змінено={changed} з {len(targets)}. Report: {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
