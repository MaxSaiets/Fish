"""
OpenAI GPT-4o-mini генератор описів та характеристик для parent-моделей.

Стратегія:
  - 1 запит на модель (не на варіант) — економія токенів
  - Вхід: family, brand, model_name, common_params, список варіантів (назви+delta-атрибути)
  - Вихід: JSON {description_html, common_params, seo_title, seo_meta}
  - Зберігаємо в meta_store.models, status='ai_draft'
  - Варіанти отримують опис автоматично через build_variant_description_html

Запуск:
  python src/ai_generator.py                        # всі pending моделі
  python src/ai_generator.py --limit 5              # перші 5 для тесту
  python src/ai_generator.py --force                # перегенерувати всі
  python src/ai_generator.py --family spinning      # тільки один тип
  python src/ai_generator.py --worker 1 --workers 3 # паралельний воркер
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(r"D:\FISH\fish-sync")
META_DB = ROOT / "data" / "meta_store.sqlite"
load_dotenv(ROOT / ".env")

API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL_NAME = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
if not API_KEY:
    sys.exit("OPENAI_API_KEY not set in .env")

# client ініціалізується в main() (може бути перевизначений через --api-key)
client: OpenAI | None = None

# ---------------------------------------------------------------------------
# Системний промпт
# ---------------------------------------------------------------------------
SYSTEM_BASE = """Ти — досвідчений копірайтер українського інтернет-магазину рибальських снастей.
Твоя задача — згенерувати SEO-оптимізовану картку товару для батьківської моделі.
Відповідай ВИКЛЮЧНО валідним JSON без markdown-обгортки, без ```json.

Формат відповіді:
{
  "description_html": "<p>...</p><p>...</p><ul><li>...</li></ul>",
  "common_params": { "Ключ": "Значення", ... },
  "seo_title": "≤70 символів",
  "seo_meta": "≤160 символів"
}

Загальні правила:
- Мова — українська, жива, конкретна, без води, без емодзі.
- description_html: 2-4 абзаци <p> + короткий <ul> переваг. 120-250 слів.
- common_params — лише поля, спільні для ВСІХ варіантів моделі.
  ВАЖЛИВО: довжина, тест, діаметр, вага варіанту — це атрибути варіантів, НЕ клади їх у common_params.
- Якщо точних даних немає — реалістичне припущення на основі бренду/класу.
- Не згадуй ціну, наявність, артикули. Не обіцяй доставку/гарантію.
"""

# ---------------------------------------------------------------------------
# Інструкції per-family
# ---------------------------------------------------------------------------
FAMILY_INSTRUCTIONS: dict[str, str] = {
    "spinning": (
        'common_params МАЄ містити (якщо відомо): "Матеріал бланка" (Carbon/IM6/IM7/IM8/скловолокно/композит), '
        '"Кількість секцій", "Транспортна довжина" (см), "Тип пропускних кілець" (SiC/Alconite/Fuji/звичайні), '
        '"Тип рукояті" (EVA/корок), "Країна-виробник". '
        "В description_html опиши призначення (ультралайт/лайт/медіум/хеві), клас проводок, цільова риба."
    ),
    "float_rod": (
        'common_params: "Матеріал бланка", "Кількість секцій", "Транспортна довжина" (см), '
        '"Тип рукояті", "Тип з\'єднання секцій" (телескоп/болонка/матч), "Країна-виробник". '
        "В description_html — стиль ловлі (поплавок/болонка/матч), цільова риба, умови застосування."
    ),
    "reel": (
        'common_params: "Тип котушки" (безінерційна/мультиплікаторна/фідерна/коропова), '
        '"Передаточне число", "Матеріал корпусу" (алюміній/графіт/магній), '
        '"Система гальма" (фронтальне/заднє), "Країна-виробник". '
        "В description_html — для якого стилю ловлі, клас котушки, намотування, ролик лісоукладача."
    ),
    "line": (
        'common_params: "Матеріал" (монофіл/плетінка/флюорокарбон), "Колір", "Країна-виробник". '
        "НЕ клади в common_params діаметр, тест, довжину — це атрибути варіантів. "
        "В description_html — гладкість, пам'ять, область застосування."
    ),
    "fluorocarbon": (
        'common_params: "Матеріал" (флюорокарбон 100%), "Колір", "Призначення" (повідець/основна), "Країна-виробник". '
        "В description_html — низька видимість у воді, твердість, стійкість до абразиву."
    ),
    "shock_leader": (
        'common_params: "Матеріал" (нейлон/флюорокарбон), "Колір", "Призначення" (шок-лідер), "Країна-виробник". '
        "В description_html — захист від зносу при далекому закиді, вузлова міцність."
    ),
    "ready_leader": (
        'common_params: "Матеріал повідця", "Тип повідця" (готовий/з гачком/з карабіном), "Країна-виробник". '
        "В description_html — кріплення, стійкість до зубів хижака, швидка заміна."
    ),
    "wobbler": (
        'common_params: "Тип воблера" (мінноу/крєнк/попер/джеркбейт/раттлін), '
        '"Плавучість" (плаваючий/тонучий/суспендер), "Матеріал" (ABS/дерево), '
        '"Кількість гачків", "Країна-виробник". '
        "В description_html — горизонт проводки, тип гри, цільова риба, рекомендована проводка."
    ),
    "spinner": (
        'common_params: "Тип блешні" (вертушка/коливалка/тел-спіннер), '
        '"Матеріал" (латунь/нікель/сталь), "Колір/покриття", "Країна-виробник". '
        "В description_html — техніка проводки, цільова риба, глибина ловлі."
    ),
    "silicone_lure": (
        'common_params: "Тип приманки" (твістер/віброхвіст/рак/черв\'як/слаг), '
        '"Матеріал" (силікон/TPE/солоний), "Колір", "Країна-виробник". '
        "В description_html — тип оснащення (джиг/офсет/дроп-шот), гра у воді, цільова риба."
    ),
    "jig_head": (
        'common_params: "Форма джиг-головки" (кулька/сапожок/шатал), "Матеріал гачка", "Країна-виробник". '
        "В description_html — тип оснащення силіконової приманки, кут атаки."
    ),
    "balancer": (
        'common_params: "Матеріал" (свинець/олово/вольфрам), "Колір/розмальовка", '
        '"Тип хвоста" (з тройником/без), "Країна-виробник". '
        "В description_html — горизонтальна гра, пауза, глибина, цільова риба (судак/щука/окунь)."
    ),
    "jig_winter": (
        'common_params: "Матеріал" (вольфрам/свинець), "Форма" (краплинка/мурашка/гвоздик/ромбік), '
        '"Тип кріплення" (вертикальне/горизонтальне), "Країна-виробник". '
        "В description_html — швидкість тонення, гра, цільова риба (окунь/плітка/йорж)."
    ),
    "hook": (
        'common_params: "Тип" (офсетний/карповий/одинарний/трійник/двійник), '
        '"Матеріал" (вуглецева сталь/нержавійка), '
        '"Покриття" (тефлон/нікель/чорний нікель), "Країна-виробник". '
        "В description_html — геометрія гачка, тип загину, вушко, область застосування."
    ),
    "nod": (
        'common_params: "Матеріал" (лавсан/метал/флюорокарбон), "Тип" (пружний/жорсткий), '
        '"Колір", "Країна-виробник". '
        "В description_html — чутливість, кут нахилу, стійкість до морозу."
    ),
    "bite_indicator": (
        'common_params: "Тип" (електронний/механічний/свингер/хангер), '
        '"Колір підсвічування", "Країна-виробник". '
        "В description_html — гучність сигналу, кріплення, чутливість регулювання."
    ),
    "rod_rest_accessory": (
        'common_params: "Тип" (підставка/рогатка/тринога/поличка), "Матеріал", "Кріплення", "Країна-виробник". '
        "В description_html — регулювання висоти/кута, сумісність, де застосовується."
    ),
    "grain_bait": (
        'common_params: "Склад/аромат", "Тип" (зерно/дип/бустер), "Країна-виробник". '
        "В description_html — сезон, техніка застосування, цільова риба (короп/лящ)."
    ),
    "boilie": (
        'common_params: "Аромат", "Тип" (тонучий/плаваючий/нейтральний), "Країна-виробник". '
        "В description_html — склад, карповий монтаж, волосяний монтаж."
    ),
    "pop_up_bait": (
        'common_params: "Аромат", "Колір", "Країна-виробник". '
        "В description_html — плавуча насадка, волосяний монтаж, збереження аромату."
    ),
    "pellets": (
        'common_params: "Склад/аромат", "Призначення" (годівниця/прикормка/насадка), "Країна-виробник". '
        "В description_html — повільне розчинення, аромат, застосування (фідер/карп)."
    ),
    "bait_mix": (
        'common_params: "Склад", "Аромат", "Консистенція" (суха/волога), "Призначення", "Країна-виробник". '
        "В description_html — як замішувати, ефект хмарки, цільова риба."
    ),
    "liquid_attractant": (
        'common_params: "Аромат/склад", "Форма" (спрей/дип/ліквід), "Країна-виробник". '
        "В description_html — нанесення на насадку, температурний діапазон, цільова риба."
    ),
    "other": (
        "Заповни common_params відповідно до типу товару. "
        "В description_html — що це, для чого, переваги, де застосовується."
    ),
}

# ---------------------------------------------------------------------------
# User prompt
# ---------------------------------------------------------------------------
USER_TEMPLATE = """Категорія: {family}
Бренд: {brand}
Модель: {model_name}
Вже відомі параметри: {known_params}
Варіанти ({n_variants}):
{variants_block}

{family_instruction}

Згенеруй картку товару."""


def build_user_prompt(model_row: dict, variants: list[dict]) -> str:
    family = model_row.get("family") or "other"
    try:
        known = json.loads(model_row.get("common_params_json") or "{}")
    except Exception:
        known = {}

    vb_lines: list[str] = []
    for v in variants:
        parts = [v["name_raw"]]
        attrs: list[str] = []
        if v.get("test_min") is not None and v.get("test_max") is not None:
            attrs.append(f"тест {v['test_min']:g}-{v['test_max']:g}г")
        if v.get("length_m"):
            attrs.append(f"довжина {v['length_m']:g}м")
        if v.get("action"):
            attrs.append(f"стрій {v['action']}")
        try:
            delta = json.loads(v.get("delta_params_json") or "{}")
            for k, val in delta.items():
                if val:
                    attrs.append(f"{k}: {val}")
        except Exception:
            pass
        if attrs:
            parts.append("(" + ", ".join(attrs) + ")")
        vb_lines.append("  - " + " ".join(parts))

    return USER_TEMPLATE.format(
        family=family,
        brand=model_row.get("brand") or "",
        model_name=model_row.get("model_name") or "",
        known_params=json.dumps(known, ensure_ascii=False) if known else "немає",
        n_variants=len(variants),
        variants_block="\n".join(vb_lines) or "  - (один варіант)",
        family_instruction=FAMILY_INSTRUCTIONS.get(family, FAMILY_INSTRUCTIONS["other"]),
    )


# ---------------------------------------------------------------------------
# Парсинг відповіді
# ---------------------------------------------------------------------------
JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_json_response(text: str) -> dict:
    t = JSON_FENCE_RE.sub("", text).strip()
    if not t.startswith("{"):
        m = re.search(r"\{.*\}", t, re.DOTALL)
        if m:
            t = m.group(0)
    return json.loads(t)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def fetch_pending(
    conn: sqlite3.Connection,
    force: bool,
    limit: int | None,
    family: str | None = None,
    exclude_family: str | None = None,
    worker: int = 0,
    workers: int = 1,
) -> list[sqlite3.Row]:
    conditions: list[str] = []
    if not force:
        conditions.append("(status = 'draft' OR ai_generated = 0 OR ai_generated IS NULL)")
    if family:
        conditions.append(f"family = '{family}'")
    if exclude_family:
        excl = [f"'{f.strip()}'" for f in exclude_family.split(",")]
        conditions.append(f"(family NOT IN ({','.join(excl)}) AND family IS NOT NULL)")
    if workers > 1:
        conditions.append(f"(rowid % {workers}) = {worker}")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    q = f"SELECT * FROM models {where} ORDER BY parent_key"
    if limit:
        q += f" LIMIT {int(limit)}"
    return conn.execute(q).fetchall()


def fetch_variants(conn: sqlite3.Connection, parent_key: str) -> list[dict]:
    rows = conn.execute(
        """SELECT name_raw, test_min, test_max, length_m, action, delta_params_json
           FROM variants WHERE parent_key = ?""",
        (parent_key,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Генерація
# ---------------------------------------------------------------------------
def generate_one(model_row: dict, variants: list[dict], max_retries: int = 4) -> dict:
    user_msg = build_user_prompt(model_row, variants)
    attempt = 0
    while True:
        try:
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_BASE},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            return parse_json_response(resp.choices[0].message.content)
        except Exception as e:
            msg = str(e)
            is_rate = "429" in msg or "rate_limit" in msg.lower()
            if not is_rate or attempt >= max_retries:
                raise
            m = re.search(r"Please try again in ([\d.]+)s", msg)
            wait = float(m.group(1)) + 2 if m else 30 * (attempt + 1)
            print(f"    rate-limit, retry in {wait:.0f}s (attempt {attempt+1}/{max_retries})")
            time.sleep(wait)
            attempt += 1


# ---------------------------------------------------------------------------
# Збереження
# ---------------------------------------------------------------------------
def save(conn: sqlite3.Connection, parent_key: str, result: dict) -> None:
    conn.execute(
        """
        UPDATE models
        SET description_html   = ?,
            common_params_json = ?,
            seo_title          = ?,
            seo_meta           = ?,
            status             = 'ai_draft',
            ai_generated       = 1,
            updated_at         = CURRENT_TIMESTAMP
        WHERE parent_key = ?
        """,
        (
            result.get("description_html", ""),
            json.dumps(result.get("common_params", {}), ensure_ascii=False),
            result.get("seo_title", "")[:200],
            result.get("seo_meta", "")[:300],
            parent_key,
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> None:
    global client
    ap = argparse.ArgumentParser(description="AI генератор описів (OpenAI GPT-4o-mini)")
    ap.add_argument("--limit",   type=int,   default=None,  help="макс. кількість моделей")
    ap.add_argument("--force",   action="store_true",       help="перегенерувати вже оброблені")
    ap.add_argument("--sleep",   type=float, default=0.5,   help="пауза між запитами (сек)")
    ap.add_argument("--family",         type=str, default=None, help="обробляти тільки цю family")
    ap.add_argument("--exclude-family", type=str, default=None, help="пропустити ці family (через кому)")
    ap.add_argument("--api-key",        type=str, default=None, help="перевизначити OPENAI_API_KEY")
    ap.add_argument("--worker",         type=int, default=0,    help="індекс воркера (0-based)")
    ap.add_argument("--workers",        type=int, default=1,    help="загальна кількість воркерів")
    args = ap.parse_args()

    api_key = args.api_key or API_KEY
    client = OpenAI(api_key=api_key)

    conn = sqlite3.connect(META_DB)
    conn.row_factory = sqlite3.Row

    pending = fetch_pending(conn, args.force, args.limit, args.family,
                            args.exclude_family, args.worker, args.workers)
    total = len(pending)
    tag = f" [worker {args.worker}/{args.workers}]" if args.workers > 1 else ""
    ftag = f" [family={args.family}]" if args.family else ""
    xtag = f" [exclude={args.exclude_family}]" if args.exclude_family else ""
    print(f"Pending: {total}{tag}{ftag}{xtag}")
    if total == 0:
        print("Нічого генерувати.")
        conn.close()
        return

    ok = fail = 0
    for i, row in enumerate(pending, 1):
        pk = row["parent_key"]
        variants = fetch_variants(conn, pk)
        label = f"[{i}/{total}] {pk[:60]}"
        try:
            result = generate_one(dict(row), variants)
            save(conn, pk, result)
            ok += 1
            desc_len = len(result.get("description_html", ""))
            params_n = len(result.get("common_params", {}))
            print(f"{label}  OK  desc={desc_len}ch params={params_n}")
        except Exception as e:
            fail += 1
            print(f"{label}  FAIL  {e}")
        if i < total and args.sleep > 0:
            time.sleep(args.sleep)

    print(f"\nDone: ok={ok}  fail={fail}  total={total}")
    conn.close()


if __name__ == "__main__":
    main()
