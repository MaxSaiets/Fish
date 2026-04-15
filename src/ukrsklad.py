"""
Читач бази УкрСклад7 (Firebird .tcb) через бібліотеку fdb.

УкрСклад тримає робочий .tcb через embedded Firebird, тому ми робимо
read-only снапшот файла перед кожним читанням.

fdb знаходить fbclient.dll автоматично, якщо вона в PATH або в каталозі скрипта.
Якщо fdb не може знайти dll — використовуємо ту, що йде з УкрСкладом.
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path

# --- Шляхи (адаптовані під цю установку УкрСклад7) ----------------------------
UKRSKLAD_DIR = Path(r"C:\Program Files (x86)\UkrSklad7")
# fbclient.dll з УкрСкладу 32-bit, тому для 64-bit Python використовуємо
# x64-збірку Firebird 3 embedded, скачану в tmp/fb3x64/
FBCLIENT = Path(r"D:\FISH\fish-sync\tmp\fb3x64\fbclient.dll")
LIVE_DB = Path(r"C:\ProgramData\UkrSklad7\db\Sklad.tcb")
SNAPSHOT_DIR = Path(r"D:\FISH\fish-sync\tmp")
SNAPSHOT_DB = SNAPSHOT_DIR / "sklad_snapshot.fdb"

USER = "SYSDBA"
PASSWORD = "masterkey"
CHARSET = "UTF8"

# Додаємо каталог fbclient у PATH щоб ctypes знайшла залежні dll
os.environ["PATH"] = str(FBCLIENT.parent) + os.pathsep + os.environ.get("PATH", "")

import fdb  # noqa: E402  (після PATH)


@dataclass
class Category:
    num: int
    name: str
    parent: int  # 0 = root


@dataclass
class Product:
    num: int          # внутрішній ID УкрСкладу
    kod: str          # артикул (KOD) — наш стабільний ID для фідів
    name: str
    tip: int          # ID категорії (TIP.NUM)
    cena_r: float     # роздрібна
    cena_o: float     # оптова
    proizv: str       # виробник
    ves: float        # вага
    descr_big: str    # повний опис (BLOB → text)
    visible: int
    stock: float = 0.0
    category_path: list[str] = field(default_factory=list)


# --- Підключення --------------------------------------------------------------
def take_snapshot() -> Path:
    """Копіює живу БД у tmp/snapshot, щоб не блокувати УкрСклад."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    if not LIVE_DB.exists():
        raise FileNotFoundError(f"Жива БД не знайдена: {LIVE_DB}")
    shutil.copy2(LIVE_DB, SNAPSHOT_DB)
    return SNAPSHOT_DB


def connect():
    if not SNAPSHOT_DB.exists():
        take_snapshot()
    return fdb.connect(
        database=str(SNAPSHOT_DB),
        user=USER,
        password=PASSWORD,
        charset=CHARSET,
        fb_library_name=str(FBCLIENT),
    )


def _read_blob(blob) -> str:
    if blob is None:
        return ""
    try:
        data = blob.read() if hasattr(blob, "read") else blob
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return str(data)
    except Exception:
        return ""


# --- High-level API -----------------------------------------------------------
def fetch_categories(conn) -> list[Category]:
    cur = conn.cursor()
    cur.execute("SELECT NUM, NAME, GRUPA FROM TIP WHERE VISIBLE=1 ORDER BY NUM")
    return [
        Category(num=row[0], name=row[1] or "", parent=row[2] or 0)
        for row in cur.fetchall()
    ]


def fetch_products(conn) -> list[Product]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT NUM, KOD, NAME, TIP, CENA_R, CENA_O, TOV_PROIZV, TOV_VES,
               TOV_DESCR_BIG, VISIBLE
        FROM TOVAR_NAME
        WHERE VISIBLE = 1
          AND IS_USLUGA = 0
        ORDER BY TIP, NUM
        """
    )
    out: list[Product] = []
    for row in cur.fetchall():
        out.append(
            Product(
                num=row[0],
                kod=(row[1] or "").strip(),
                name=(row[2] or "").strip(),
                tip=row[3] or 0,
                cena_r=float(row[4] or 0),
                cena_o=float(row[5] or 0),
                proizv=(row[6] or "").strip(),
                ves=float(row[7] or 0),
                descr_big=_read_blob(row[8]),
                visible=row[9] or 0,
            )
        )
    return out


def fetch_stock(conn) -> dict[int, float]:
    """Повертає {tovar_id: total_kolvo} по всіх складах."""
    cur = conn.cursor()
    cur.execute(
        "SELECT TOVAR_ID, SUM(KOLVO) FROM TOVAR_ZAL WHERE VISIBLE=1 GROUP BY TOVAR_ID"
    )
    return {row[0]: float(row[1] or 0) for row in cur.fetchall()}


def fetch_image_count(conn) -> dict[int, int]:
    """Повертає {tovar_id: image_count} — скільки фото є в БД."""
    cur = conn.cursor()
    cur.execute("SELECT TOVAR_ID, COUNT(*) FROM TOVAR_IMAGES GROUP BY TOVAR_ID")
    return {row[0]: row[1] for row in cur.fetchall()}


def dump_all(out_path: Path, refresh_snapshot: bool = True) -> dict:
    """Знімає снапшот, витягує все, пише у JSON."""
    if refresh_snapshot:
        take_snapshot()
    conn = connect()
    try:
        cats = fetch_categories(conn)
        prods = fetch_products(conn)
        stock = fetch_stock(conn)
        img_counts = fetch_image_count(conn)
    finally:
        conn.close()

    cat_by_id = {c.num: c for c in cats}

    def cat_path(tip_id: int) -> list[str]:
        path: list[str] = []
        current = cat_by_id.get(tip_id)
        guard = 0
        while current and guard < 10:
            path.append(current.name)
            if current.parent == 0:
                break
            current = cat_by_id.get(current.parent)
            guard += 1
        return list(reversed(path))

    enriched: list[dict] = []
    for p in prods:
        p.stock = stock.get(p.num, 0)
        p.category_path = cat_path(p.tip)
        d = asdict(p)
        d["image_count"] = img_counts.get(p.num, 0)
        enriched.append(d)

    payload = {
        "categories": [asdict(c) for c in cats],
        "products": enriched,
        "stats": {
            "categories": len(cats),
            "products": len(prods),
            "with_stock": sum(1 for d in enriched if d["stock"] > 0),
            "with_images": sum(1 for d in enriched if d["image_count"] > 0),
            "with_price": sum(1 for d in enriched if d["cena_r"] > 0),
            "with_descr": sum(1 for d in enriched if d["descr_big"]),
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload["stats"]


if __name__ == "__main__":
    stats = dump_all(Path(r"D:\FISH\fish-sync\data\products.json"))
    print("OK:", stats)
