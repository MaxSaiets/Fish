"""
SQLite-сховище для збагаченого контенту, якого немає в УкрСкладі:
  - бренд, повний опис (HTML), SEO-поля
  - характеристики (виробник, кастинг, вага...) на рівні моделі
  - характеристики delta на рівні варіанта
  - URL фотографій (після завантаження на VPS / або base64 inline)
  - status (draft / approved / rejected) для модерації

Ключ моделі — parent_key з group_models.py.
Ключ варіанта — kod (артикул з УкрСкладу).
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(r"D:\FISH\fish-sync\data\meta_store.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS models (
    parent_key   TEXT PRIMARY KEY,
    family       TEXT DEFAULT '',
    type_word    TEXT NOT NULL,            -- "Спінінг", "Котушка"...
    brand        TEXT NOT NULL,
    model_name   TEXT NOT NULL,
    display_name TEXT NOT NULL,
    category_tip INTEGER DEFAULT 0,
    source_category TEXT DEFAULT '',
    description_html TEXT DEFAULT '',
    common_params_json TEXT DEFAULT '{}',  -- {"Виробник": "KAIDA", "Матеріал": "Карбон"}
    seo_title    TEXT DEFAULT '',
    seo_meta     TEXT DEFAULT '',
    status       TEXT DEFAULT 'draft',     -- draft | approved | rejected
    ai_generated INTEGER DEFAULT 0,
    created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at   TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS variants (
    kod          TEXT PRIMARY KEY,         -- артикул УкрСкладу
    parent_key   TEXT NOT NULL,
    name_raw     TEXT NOT NULL,
    test_min     REAL,
    test_max     REAL,
    length_m     REAL,
    action       TEXT,
    delta_params_json TEXT DEFAULT '{}',
    pictures_json TEXT DEFAULT '[]',       -- ["https://...jpg", ...]
    FOREIGN KEY (parent_key) REFERENCES models(parent_key)
);

CREATE INDEX IF NOT EXISTS idx_variants_parent ON variants(parent_key);
"""


@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as c:
        c.executescript(SCHEMA)
        columns = {row["name"] for row in c.execute("PRAGMA table_info(models)").fetchall()}
        if "family" not in columns:
            c.execute("ALTER TABLE models ADD COLUMN family TEXT DEFAULT ''")
        if "category_tip" not in columns:
            c.execute("ALTER TABLE models ADD COLUMN category_tip INTEGER DEFAULT 0")
        if "source_category" not in columns:
            c.execute("ALTER TABLE models ADD COLUMN source_category TEXT DEFAULT ''")


def import_from_models_json(models_json: Path) -> dict:
    """
    Заливає parent+variants з models.json у meta_store.
    Існуючі рядки оновлюються тільки в полях ідентичності — НЕ затирає
    description_html, common_params_json (їх редагує AI/користувач).
    """
    init_db()
    data = json.loads(models_json.read_text(encoding="utf-8"))
    inserted_models = updated_models = inserted_variants = 0

    with get_conn() as c:
        for m in data["models"]:
            pk = m["parent_key"]
            suggested_common = json.dumps(m.get("common_params") or {}, ensure_ascii=False)
            row = c.execute("SELECT 1 FROM models WHERE parent_key = ?", (pk,)).fetchone()
            if row:
                c.execute(
                    """
                    UPDATE models SET
                        family = ?, type_word = ?, brand = ?, model_name = ?, display_name = ?,
                        category_tip = ?, source_category = ?,
                        common_params_json = CASE
                            WHEN COALESCE(common_params_json, '{}') IN ('', '{}') THEN ?
                            ELSE common_params_json
                        END,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE parent_key = ?
                    """,
                    (
                        m.get("family", ""),
                        m["type_word"],
                        m["brand"],
                        m["model_name"],
                        m["display_name"],
                        m.get("category_tip", 0),
                        m.get("source_category", ""),
                        suggested_common,
                        pk,
                    ),
                )
                updated_models += 1
            else:
                c.execute(
                    """
                    INSERT INTO models (
                        parent_key, family, type_word, brand, model_name, display_name,
                        category_tip, source_category, common_params_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pk,
                        m.get("family", ""),
                        m["type_word"],
                        m["brand"],
                        m["model_name"],
                        m["display_name"],
                        m.get("category_tip", 0),
                        m.get("source_category", ""),
                        suggested_common,
                    ),
                )
                inserted_models += 1

            for v in m["variants"]:
                kod = v["kod"]
                if not kod:
                    continue
                c.execute(
                    """
                    INSERT INTO variants (
                        kod, parent_key, name_raw, test_min, test_max, length_m, action, delta_params_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(kod) DO UPDATE SET
                        parent_key = excluded.parent_key,
                        name_raw   = excluded.name_raw,
                        test_min   = excluded.test_min,
                        test_max   = excluded.test_max,
                        length_m   = excluded.length_m,
                        action     = excluded.action,
                        delta_params_json = excluded.delta_params_json
                    """,
                    (
                        kod,
                        pk,
                        v["name_raw"],
                        v.get("test_min"),
                        v.get("test_max"),
                        v.get("length_m"),
                        v.get("action"),
                        json.dumps(v.get("delta_params") or {}, ensure_ascii=False),
                    ),
                )
                inserted_variants += 1

    return {
        "models_inserted": inserted_models,
        "models_updated": updated_models,
        "variants_upserted": inserted_variants,
    }


def fetch_all_models() -> list[dict]:
    with get_conn() as c:
        rows = c.execute(
            """
            SELECT m.*,
                   COUNT(v.kod) AS variant_count
            FROM models m
            LEFT JOIN variants v ON v.parent_key = m.parent_key
            GROUP BY m.parent_key
            ORDER BY m.brand, m.model_name
            """
        ).fetchall()
        return [dict(r) for r in rows]


def fetch_variants_for(parent_key: str) -> list[dict]:
    with get_conn() as c:
        rows = c.execute(
            "SELECT * FROM variants WHERE parent_key = ? ORDER BY kod",
            (parent_key,),
        ).fetchall()
        return [dict(r) for r in rows]


if __name__ == "__main__":
    stats = import_from_models_json(Path(r"D:\FISH\fish-sync\data\models.json"))
    print("OK:", stats)
    models = fetch_all_models()
    print(f"Total in DB: {len(models)} models")
