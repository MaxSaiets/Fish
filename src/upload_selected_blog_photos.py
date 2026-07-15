# -*- coding: utf-8 -*-
"""
Крок 2: залити ВРУЧНУ ВІДІБРАНІ (візуально перевірені) фото для 8 статей
блогу, яким бракувало фото. Кандидати підготовлені в
public/blog-missing-photo-candidates/ скриптами prepare_missing_blog_photo_candidates*.py
і додатковими точковими запитами; вибір зроблено вручну після перегляду
кожного кандидата.

  python src/upload_selected_blog_photos.py
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import requests
import urllib3

from fill_horoshop_content_pages import load_env, parse_form_payload
from replace_blog_images_openverse import replace_figures, retry_get, retry_post, upload_editor_image

urllib3.disable_warnings()

CAND_DIR = ROOT / "public" / "blog-missing-photo-candidates"
REPORT = ROOT / "data" / "blog_missing_photo_upload_report_20260713.json"

# id -> (hero_filename, body_filename)
SELECTION: dict[str, tuple[str, str]] = {
    "135": ("art135v2_4.jpg", "art135v2_1.jpg"),
    "136": ("art_sauger.jpg", "art136v2_1.jpg"),
    "137": ("art137_pick_thornwick.jpg", "art137_pick_andes.jpg"),
    "138": ("art138_carpnet.jpg", "art_crappie_net.jpg"),
    "139": ("art139v2_3.jpg", "art139v2_4.jpg"),
    "140": ("art_andes_10.jpg", "art141_2.jpg"),
    "141": ("art141v2_5.jpg", "art_bluelake.jpg"),
    "142": ("art142_1.jpg", "art142_3.jpg"),
}

TITLES: dict[str, str] = {
    "135": "Балансир взимку: як розловити і не розчаруватись",
    "136": "Силікон на судака і окуня: розмір, колір і їстівність",
    "137": "PVA-сітка і стіки: точкова подача, яка реально працює",
    "138": "Підсак, мат і антисептик: культура поводження з трофеєм",
    "139": "Волосінь, шнур чи флюорокарбон: що ставити і коли",
    "140": "Електронний сигналізатор чи свінгер: що обрати на коропову сесію",
    "141": "Крісло, столик і порядок на точці: облаштування місця рибалки",
    "142": "Перший лід без помилок: спорядження і безпека зимової риболовлі",
}


def main() -> int:
    env = load_env()
    base_url = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-blog-photo-upload/1.0"
    session.post(
        f"{base_url}/core-api/admin/security/login",
        json={"login": env["HOROSHOP_LOGIN"], "password": env["HOROSHOP_PASS"]},
        timeout=60,
        verify=False,
    ).raise_for_status()

    results = []
    for record_id, (hero_name, body_name) in SELECTION.items():
        hero_path = CAND_DIR / hero_name
        body_path = CAND_DIR / body_name
        assert hero_path.exists(), hero_path
        assert body_path.exists(), body_path

        hero_url = upload_editor_image(session, base_url, hero_path)
        body_url = upload_editor_image(session, base_url, body_path)

        edit_url = f"{base_url}/adminLegacy/edit.php?id={record_id}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
        response = retry_get(session, edit_url, timeout=60, verify=False)
        response.raise_for_status()
        payload = parse_form_payload(response.text)
        body = payload.get("names[i18n][3][text]", "")
        title = TITLES[record_id]
        new_body = replace_figures(body, hero_url, body_url, title)
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
        files = {"names[img][file]": (hero_path.name, hero_path.open("rb"), "image/jpeg")}
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
        results.append({
            "id": record_id,
            "title": title,
            "hero_source": hero_name,
            "body_source": body_name,
            "hero_uploaded": hero_url,
            "body_uploaded": body_url,
            "status": save.status_code,
        })
        print(f"  id={record_id} status={save.status_code} :: {title}", flush=True)

    # verify
    verify = []
    for record_id in SELECTION:
        edit_url = f"{base_url}/adminLegacy/edit.php?id={record_id}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
        response = retry_get(session, edit_url, timeout=60, verify=False)
        payload = parse_form_payload(response.text)
        preview = payload.get("names[img][value]", "")
        verify.append({"id": record_id, "preview_set": bool(preview)})
        print(f"  verify id={record_id} preview_set={bool(preview)}", flush=True)

    REPORT.write_text(json.dumps({"results": results, "verify": verify}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport: {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
