"""
Gemini-генератор описів та характеристик для parent-моделей.

Стратегія:
  - 1 запит на модель (не на варіант) — економія токенів
  - Вхід: type_word, brand, model_name, список варіантів (назви+delta-атрибути)
  - Вихід: JSON {description_html, common_params, seo_title, seo_meta}
  - Зберігаємо в meta_store.models, status='ai_draft' (для майбутньої модерації)

Запуск:
  python src/ai_generator.py              # всі моделі зі status='draft'
  python src/ai_generator.py --limit 3    # перші 3 для smoke-тесту
  python src/ai_generator.py --force      # перегенерувати навіть ai_draft/approved
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
import google.generativeai as genai

ROOT = Path(r"D:\FISH\fish-sync")
META_DB = ROOT / "data" / "meta_store.sqlite"
load_dotenv(ROOT / ".env")

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
if not API_KEY:
    sys.exit("GEMINI_API_KEY not set in .env")

genai.configure(api_key=API_KEY)

SYSTEM_PROMPT = """Ти — копірайтер українського інтернет-магазину рибальських снастей "Все для рибалки" (Раково).
Твоя задача — згенерувати SEO-оптимізовану картку товару для батьківської моделі спінінга/вудилища/котушки.
Відповідай ВИКЛЮЧНО валідним JSON без markdown-обгортки, без ```json.

Формат:
{
  "description_html": "<p>...</p><p>...</p><ul><li>...</li></ul>",
  "common_params": {
    "Матеріал бланка": "...",
    "Кількість секцій": "...",
    "Транспортна довжина": "...",
    "Тип пропускних кілець": "...",
    "Тип рукояті": "...",
    "Країна-виробник": "..."
  },
  "seo_title": "≤70 символів",
  "seo_meta": "≤160 символів"
}

Правила:
- Мова — українська, жива, без води, без емодзі.
- description_html: 2-4 абзаци <p> + короткий <ul> переваг. 120-250 слів.
- common_params — лише ті поля, які логічно однакові для всіх варіантів моделі (не тест і не довжина — це атрибути варіантів).
- Якщо даних для поля в common_params немає — став реалістичне припущення на основі бренду/класу снасті, але не вигадуй номери стандартів.
- Не згадуй ціну, наявність, конкретні артикули.
- Не обіцяй доставку/гарантію.
"""

USER_TEMPLATE = """Тип: {type_word}
Бренд: {brand}
Модель: {model_name}
Варіанти ({n_variants}):
{variants_block}

Згенеруй картку."""


def build_user_prompt(model_row: dict, variants: list[dict]) -> str:
    vb_lines = []
    for v in variants:
        parts = [v["name_raw"]]
        attrs = []
        if v.get("test_min") is not None and v.get("test_max") is not None:
            attrs.append(f"тест {v['test_min']:g}-{v['test_max']:g}г")
        if v.get("length_m"):
            attrs.append(f"довжина {v['length_m']:g}м")
        if v.get("action"):
            attrs.append(f"лад {v['action']}")
        if attrs:
            parts.append("(" + ", ".join(attrs) + ")")
        vb_lines.append("  - " + " ".join(parts))
    return USER_TEMPLATE.format(
        type_word=model_row["type_word"],
        brand=model_row["brand"],
        model_name=model_row["model_name"],
        n_variants=len(variants),
        variants_block="\n".join(vb_lines),
    )


JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_json_response(text: str) -> dict:
    t = JSON_FENCE_RE.sub("", text).strip()
    # fallback — виділити першу {...} групу
    if not t.startswith("{"):
        m = re.search(r"\{.*\}", t, re.DOTALL)
        if m:
            t = m.group(0)
    return json.loads(t)


def fetch_pending(conn: sqlite3.Connection, force: bool, limit: int | None) -> list[sqlite3.Row]:
    where = "" if force else "WHERE status = 'draft' OR ai_generated = 0"
    q = f"SELECT * FROM models {where} ORDER BY parent_key"
    if limit:
        q += f" LIMIT {int(limit)}"
    return conn.execute(q).fetchall()


def fetch_variants(conn: sqlite3.Connection, parent_key: str) -> list[dict]:
    rows = conn.execute(
        "SELECT name_raw, test_min, test_max, length_m, action FROM variants WHERE parent_key = ?",
        (parent_key,),
    ).fetchall()
    return [dict(r) for r in rows]


def generate_one(model, model_row: dict, variants: list[dict], max_retries: int = 4) -> dict:
    user = build_user_prompt(model_row, variants)
    attempt = 0
    while True:
        try:
            resp = model.generate_content(
                [SYSTEM_PROMPT, user],
                generation_config={"temperature": 0.7, "response_mime_type": "application/json"},
            )
            return parse_json_response(resp.text)
        except Exception as e:
            msg = str(e)
            if "429" not in msg or attempt >= max_retries:
                raise
            # витягуємо retry_delay з тексту помилки
            m = re.search(r"seconds:\s*(\d+)", msg)
            wait = int(m.group(1)) + 2 if m else 30 * (attempt + 1)
            print(f"    429 rate-limit, retry in {wait}s (attempt {attempt+1}/{max_retries})")
            time.sleep(wait)
            attempt += 1


def save(conn: sqlite3.Connection, parent_key: str, result: dict) -> None:
    conn.execute(
        """
        UPDATE models
        SET description_html = ?,
            common_params_json = ?,
            seo_title = ?,
            seo_meta = ?,
            status = 'ai_draft',
            ai_generated = 1,
            updated_at = CURRENT_TIMESTAMP
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--sleep", type=float, default=2.0, help="пауза між запитами (сек), free tier ~15 RPM")
    args = ap.parse_args()

    model = genai.GenerativeModel(MODEL_NAME)
    conn = sqlite3.connect(META_DB)
    conn.row_factory = sqlite3.Row

    pending = fetch_pending(conn, args.force, args.limit)
    print(f"Pending models: {len(pending)}")

    ok = fail = 0
    for i, row in enumerate(pending, 1):
        pk = row["parent_key"]
        variants = fetch_variants(conn, pk)
        try:
            result = generate_one(model, dict(row), variants)
            save(conn, pk, result)
            ok += 1
            print(f"[{i}/{len(pending)}] ✓ {pk} — {len(result.get('description_html',''))} chars")
        except Exception as e:
            fail += 1
            print(f"[{i}/{len(pending)}] ✗ {pk} — {e}")
        if i < len(pending):
            time.sleep(args.sleep)

    print(f"\nDone: ok={ok} fail={fail}")
    conn.close()


if __name__ == "__main__":
    main()
