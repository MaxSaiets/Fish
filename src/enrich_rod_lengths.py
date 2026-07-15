# -*- coding: utf-8 -*-
"""
Довжина + Матеріал для вудилищ через імпорт характеристик (import_type=characteristics).

Правила витягування довжини (тільки безпечні, нічого не вигадуємо):
  1. Локальний параметр "Довжина" (як є, з УкрСкладу/збагачення).
  2. Явне "X.XX" / "X,XX" у назві (1.00-9.99) -> X.XX м.
  3. Явне "X м" / "X.X м".
  4. "NNN/S" (360/3) -> 3.6 м + S секцій.
  5. Тризначне NNN кратне 10 (180-800) -> N.N м, ЯКЩО не частина діапазону
     тесту (5-400) і не перед "г".
  6. "N000" (4000-8000, вудочки-серійники: NEW HUNTER 5000) -> N.0 м.

Матеріал: локальний параметр "Матеріал"/"Матеріал бланка", нормалізований
(carbon->Карбон, carbon imN->Карбон IMN).

  python src/enrich_rod_lengths.py --dry-run     # тільки списки
  python src/enrich_rod_lengths.py --sample      # імпорт 5 товарів
  python src/enrich_rod_lengths.py               # повний імпорт
"""
from __future__ import annotations

import argparse
import html as html_mod
import io
import json
import re
import sys
from pathlib import Path

# stdout загортає import_parent_brand при імпорті — тут не чіпаємо (інакше closed file)
ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

from import_parent_brand import ART_TD, build_xls, run_import  # noqa: E402
from sync_content_playwright import load_env  # noqa: E402

ROD_WORD = re.compile(r"^(Спінінг|Спиннинг|Спіннінг|Вудк|Вудочк|Вудилищ|Удилищ|Фідер|Пікер|Мах)", re.I)
EXCLUDE = re.compile(r"Годівниц|Коліно|коліно|Кінчик|Вершинка|Квівертип|Тюльпан|Кільце|Кільця", re.I)

RE_M = re.compile(r"(?<![\d.,])([1-9](?:[.,]\d{1,2})?)\s*(?:м|m)\b", re.I)
RE_DOT = re.compile(r"(?<![\d.,])([1-9][.,]\d{2})(?![\d])")
RE_SLASH = re.compile(r"(?<![\d.,])([1-8]\d0)\s*/\s*(\d)(?![\d])")
RE_NNN = re.compile(r"(?<![\d.,\-–])([1-8]\d0)(?!\s*[-–]\s*\d)(?!\s*г)(?![\d.,])")
RE_N000 = re.compile(r"(?<![\d.,\-–])([4-8])000(?![\d.,\-–])")

_MAT_MAP = [
    (re.compile(r"\bcarbon\b[\s/]*im\s?(\d+)", re.I), lambda m: f"Карбон IM{m.group(1)}"),
    (re.compile(r"^carbon$", re.I), lambda m: "Карбон"),
    (re.compile(r"^composite$", re.I), lambda m: "Композит"),
    (re.compile(r"^fiberglass$", re.I), lambda m: "Скловолокно"),
]


_MAT_FIXES = {
    "кардон": "Карбон",  # одруківка в УкрСкладі
    "карбон": "Карбон",
    "композит": "Композит",
    "скловолокно": "Скловолокно",
    "пластик": "Пластик",
    "карбон / композит": "Карбон / композит",
}


def norm_material(v: str) -> str:
    v = v.strip()
    for rx, fn in _MAT_MAP:
        m = rx.search(v)
        if m:
            return fn(m)
    fixed = _MAT_FIXES.get(v.lower())
    if fixed:
        return fixed
    return v[:1].upper() + v[1:] if v else v


def fmt_len(val: float) -> str:
    s = f"{val:.2f}".rstrip("0").rstrip(".")
    return f"{s} м"


def extract_len(name: str) -> tuple[str, str]:
    """-> (довжина, к-сть секцій або '')"""
    m = RE_M.search(name)
    if m:
        v = float(m.group(1).replace(",", "."))
        if 1.0 <= v <= 9.99:
            return fmt_len(v), ""
    m = RE_DOT.search(name)
    if m:
        v = float(m.group(1).replace(",", "."))
        if 1.0 <= v <= 9.99:
            return fmt_len(v), ""
    m = RE_SLASH.search(name)
    if m:
        v = int(m.group(1)) / 100
        if 1.8 <= v <= 8.0:
            return fmt_len(v), m.group(2)
    m = RE_NNN.search(name)
    if m:
        v = int(m.group(1)) / 100
        if 1.8 <= v <= 8.0:
            return fmt_len(v), ""
    m = RE_N000.search(name)
    if m:
        return fmt_len(float(m.group(1))), ""
    return "", ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()

    from horoshop_catalog import build_canonical_products
    prods = build_canonical_products()

    rows_data = []  # (article, dovzhyna, material, sekcii)
    for p in prods:
        name = (p.get("title") or "").strip()
        if not ROD_WORD.search(name) or EXCLUDE.search(name):
            continue
        params = {x["name"]: x["value"] for x in (p.get("params") or []) if isinstance(x, dict)}
        length = (params.get("Довжина") or "").strip()
        sekcii = ""
        if not length:
            length, sekcii = extract_len(name)
        material = norm_material(params.get("Матеріал") or params.get("Матеріал бланка") or "")
        if not length and not material:
            continue
        rows_data.append((str(p.get("article")).strip(), length, material, sekcii))

    n_len = sum(1 for r in rows_data if r[1])
    n_mat = sum(1 for r in rows_data if r[2])
    n_sek = sum(1 for r in rows_data if r[3])
    print(f"рядків: {len(rows_data)} | з довжиною: {n_len} | з матеріалом: {n_mat} | з секціями: {n_sek}")

    if args.dry_run:
        for r in rows_data[:25]:
            print("  ", r)
        return 0

    if args.sample:
        # 5 показових: 4095 (NEW HUNTER 5000) + перші 4 з довжиною з назви
        sample_arts = {"4095"}
        for r in rows_data:
            if r[1] and r[0] not in sample_arts:
                sample_arts.add(r[0])
            if len(sample_arts) >= 5:
                break
        rows_data = [r for r in rows_data if r[0] in sample_arts]
        print("sample:", rows_data)

    rows = []
    for art, ln, mat, sek in rows_data:
        rows.append(
            f"<tr>{ART_TD}{html_mod.escape(art)}</td>"
            f"<td>{html_mod.escape(ln)}</td>"
            f"<td>{html_mod.escape(mat)}</td></tr>"
        )
    xls = build_xls(rows, ["Артикул", "Довжина", "Матеріал"])
    out = ROOT / "tmp" / "import_rod_lengths.xls"
    out.write_bytes(xls)
    print(f"XLS: {out} ({len(rows)} рядків)")

    env = load_env()
    base = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    res = run_import(out, ["article", "dovzhyna", "material"], base,
                     env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"],
                     import_type="characteristics", handler="381")
    print("Результат:", res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
