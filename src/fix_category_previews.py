# -*- coding: utf-8 -*-
"""
Заміна дубльованих/невідповідних прев'ю-фото категорій на головній.
Знайдені дублі: Херабуна=Котушки (та сама котушка), Чохли=Туризм (той самий намет),
Гачки=Готові монтажі (той самий воблер). Замінюємо 4 категорії реальними фото.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

from apply_horoshop_menu_fixes import auth, fetch_full_form_payload, get_base_url, load_env, post_form  # noqa: E402

SCRATCH = Path(r"C:\Users\sayet\AppData\Local\Temp\claude\D--FISH\1b16c474-a7bb-4165-a51f-f6ce2f363819\scratchpad")

TARGETS = [
    ("1234", "97", "kherabuna.jpg"),
    ("1238", "97", "chokhly.jpg"),
    ("1099", "97", "hachky.jpg"),
    ("1096", "97", "hotovi-montazhi.jpg"),
]


def replace_preview(session, base_url: str, cid: str, parent: str, img_path: Path) -> None:
    payload = fetch_full_form_payload(session, base_url, cid, parent)
    payload.pop("extra_parent[image][file]", None)
    files = {"extra_parent[image][file]": (img_path.name, img_path.read_bytes(), "image/jpeg")}
    payload["checkcode"] = "yamete_kudasai"
    payload["id"] = cid
    payload["handler"] = "4"
    payload["handlertable"] = "pages"
    payload["back"] = "index.php"
    payload["names[parent]"] = parent
    r = session.post(
        f"{base_url}/adminLegacy/save.php",
        data=payload, files=files,
        headers={"X-Requested-With": "XMLHttpRequest",
                 "Referer": f"{base_url}/adminLegacy/edit.php?id={cid}&parent={parent}&handler=4"},
        timeout=60, verify=False,
    )
    print(f"  {cid}: status={r.status_code} len={len(r.text)}")


def main() -> int:
    env = load_env()
    base = get_base_url(env)
    s = requests.Session()
    s.headers["User-Agent"] = "fish-sync-cat-preview-fix/1.0"
    auth(s, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    for cid, parent, fname in TARGETS:
        img = SCRATCH / f"newpreview_{fname.split('.')[0].replace('hotovi-montazhi','hotovi-montazhi')}.jpg"
        # normalize filenames from earlier download step
        alt = {
            "1234": SCRATCH / "newpreview_kherabuna.jpg",
            "1238": SCRATCH / "newpreview_chokhly.jpg",
            "1099": SCRATCH / "newpreview_hachky.jpg",
            "1096": SCRATCH / "newpreview_hotovi-montazhi.jpg",
        }[cid]
        print(f"Категорія {cid}: {alt}")
        replace_preview(s, base, cid, parent, alt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
