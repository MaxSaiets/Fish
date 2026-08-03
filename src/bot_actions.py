# -*- coding: utf-8 -*-
"""
Дії бота: заливка фото з Telegram, черга фотографування, перевірка системи.

Логіка навмисно винесена сюди, щоб її можна було тестувати без aiogram
(на dev-машині бот не встановлений) — обробники в telegram_bot.py лишаються тонкими.
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings()

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / "tmp" / "bot_photos"
PHOTO_PRIORITY_CSV = ROOT / "data" / "photo_priority_ONLINE_20260717.csv"
PHOTO_AUDIT = ROOT / "data" / "real_photo_audit_v2_full.json"
PHOTO_LOG = ROOT / "data" / "bot_photo_uploads.json"


def _env() -> dict:
    env: dict[str, str] = {}
    ef = ROOT / ".env"
    if ef.exists():
        for line in ef.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def _base_url(env: dict) -> str:
    return (env.get("HOROSHOP_BASE_URL") or "https://vsedliarybalky.com.ua").rstrip("/")


# ────────────────────────── ФОТО ──────────────────────────

def upload_photo_for_article(article: str, src_path: str | Path,
                             clean_gallery: bool = False) -> tuple[bool, str]:
    """Заливає одне фото на товар за артикулом.

    Механізм той самий, що в upload_horoshop_images.py:
      ім'я файлу <артикул>@<мітка>.jpg → check → upload → assign.
    clean_gallery=True замінює всю галерею (щоб прибрати заглушку).
    """
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from upload_horoshop_images import (
        admin_login, fetch_import_metadata, check_images, upload_image,
        assign_images, with_retry,
    )

    article = str(article).strip()
    if not article:
        return False, "Не вказано артикул."
    src = Path(src_path)
    if not src.is_file():
        return False, f"Файл не знайдено: {src}"

    TMP.mkdir(parents=True, exist_ok=True)
    suffix = src.suffix.lower() or ".jpg"
    if suffix not in (".jpg", ".jpeg", ".png", ".webp"):
        return False, f"Непідтримуваний формат: {suffix}"
    staged = TMP / f"{article}@{datetime.now():%Y%m%d_%H%M%S}{suffix}"
    shutil.copy2(src, staged)

    env = _env()
    base = _base_url(env)
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-bot/1.0"
    try:
        admin_login(session, base, env.get("HOROSHOP_LOGIN", ""),
                    env.get("HOROSHOP_PASS", ""), 60)
        tokens = fetch_import_metadata(session, base, 60)

        checked = with_retry(check_images, session, tokens["project_jwt"], [staged.name], 60)
        meta = (checked.get("data") or {}).get(staged.name) or {}
        if not meta.get("success"):
            reason = meta.get("message") or meta.get("error") or "артикул не знайдено на сайті"
            return False, f"Сайт не прийняв файл: {reason}"

        uploaded = with_retry(upload_image, session, tokens["aws_endpoint"],
                              tokens["cloud_token"], staged, meta, 120)
        payload = [{
            "handler": meta.get("handler") or "",
            "param": meta.get("param") or "",
            "parent": meta.get("parent") or "",
            "uri": uploaded["uri"],
            "width": uploaded["width"],
            "height": uploaded["height"],
            "fileSize": uploaded["fileSize"],
            "sortOrder": 0,
        }]
        with_retry(assign_images, session, tokens["project_jwt"], payload, clean_gallery, 60)
    except Exception as exc:  # noqa: BLE001
        return False, f"Помилка заливки: {exc}"
    finally:
        try:
            staged.unlink(missing_ok=True)
        except OSError:
            pass

    _log_upload(article)
    return True, f"Фото залито на товар {article}."


def _log_upload(article: str) -> None:
    log = []
    if PHOTO_LOG.exists():
        try:
            log = json.loads(PHOTO_LOG.read_text(encoding="utf-8"))
        except Exception:
            log = []
    log.append({"article": article, "at": datetime.now().isoformat(timespec="seconds")})
    PHOTO_LOG.parent.mkdir(parents=True, exist_ok=True)
    PHOTO_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")


def photo_progress() -> dict:
    """Скільки пріоритетних товарів уже відзнято через бота."""
    done = []
    if PHOTO_LOG.exists():
        try:
            done = json.loads(PHOTO_LOG.read_text(encoding="utf-8"))
        except Exception:
            done = []
    todo_total = 0
    if PHOTO_PRIORITY_CSV.exists():
        with PHOTO_PRIORITY_CSV.open(encoding="utf-8-sig") as fh:
            todo_total = sum(1 for _ in csv.DictReader(fh))
    uploaded_articles = {str(d.get("article")) for d in done}
    return {"uploaded": len(uploaded_articles), "priority_total": todo_total}


def photo_todo(limit: int = 10) -> list[dict]:
    """Наступні товари на фотографування: найбільша виручка, є в наявності, фото — заглушка."""
    if not PHOTO_PRIORITY_CSV.exists():
        return []
    done = set()
    if PHOTO_LOG.exists():
        try:
            done = {str(d.get("article")) for d in json.loads(PHOTO_LOG.read_text(encoding="utf-8"))}
        except Exception:
            done = set()
    rows = []
    with PHOTO_PRIORITY_CSV.open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            art = (r.get("Артикул") or "").strip()
            if not art or art in done:
                continue
            rows.append({
                "article": art,
                "name": (r.get("Назва") or "")[:42],
                "revenue": r.get("Виручка") or r.get("Виручка,грн") or "",
                "stock": r.get("Залишок") or "",
            })
            if len(rows) >= limit:
                break
    return rows


def photo_todo_html(limit: int = 10) -> str:
    rows = photo_todo(limit)
    prog = photo_progress()
    if not rows:
        return "✅ Пріоритетний список відзнято повністю."
    lines = [
        "📸 <b>ЩО ФОТОГРАФУВАТИ ДАЛІ</b>",
        f"<i>Залито через бота: {prog['uploaded']} з {prog['priority_total']} пріоритетних</i>",
        "",
        "Надішліть фото сюди, у підпис — артикул.",
        "",
    ]
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. <code>{r['article']}</code> — {r['name']}")
        if r["revenue"]:
            lines.append(f"     продано на {r['revenue']} грн · залишок {r['stock']}")
    return "\n".join(lines)


def prepare_photo(src_path: str | Path) -> str:
    """Готує фото до заливки: RGB JPEG, менша сторона ≥1000px (вимога Rozetka).

    Telegram стискає фото до ~1280px по більшій стороні, тому менша сторона
    часто < 1000 — акуратно масштабуємо вгору. Повертає шлях до готового файлу.
    """
    from PIL import Image

    src = Path(src_path)
    im = Image.open(src)
    im = im.convert("RGB")
    w, h = im.size
    if min(w, h) < 1000:
        scale = 1000 / min(w, h)
        im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    out = src.with_name(src.stem + "_ready.jpg")
    im.save(out, "JPEG", quality=90)
    return str(out)


# ────────────────────────── AI-ОПИСИ (пакетна модерація) ──────────────────────────

def bulk_approve_stats() -> dict:
    """Скільки ai_draft описів пройшли б фільтри якості (без запису)."""
    return _bulk_approve(dry_run=True)


def bulk_approve_ai() -> dict:
    """Затверджує всі ai_draft, що проходять ті самі фільтри якості,
    які застосовує рендер (has_suspicious_text / has_low_quality_description).
    Неякісні лишаються в ai_draft на ручну перевірку. Оборотно (це лише статус)."""
    return _bulk_approve(dry_run=False)


def _bulk_approve(dry_run: bool) -> dict:
    import sqlite3
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from horoshop_catalog import has_low_quality_description, has_suspicious_text

    conn = sqlite3.connect(ROOT / "data" / "meta_store.sqlite")
    rows = conn.execute(
        "SELECT parent_key, description_html FROM models WHERE status = 'ai_draft'"
    ).fetchall()
    good, bad = [], []
    for pk, desc in rows:
        desc = desc or ""
        if desc and not has_suspicious_text(desc) and not has_low_quality_description(desc):
            good.append(pk)
        else:
            bad.append(pk)
    if not dry_run and good:
        conn.executemany(
            "UPDATE models SET status = 'approved', updated_at = CURRENT_TIMESTAMP "
            "WHERE parent_key = ?",
            [(pk,) for pk in good],
        )
        conn.commit()
    conn.close()
    return {"total": len(rows), "approved": len(good), "left": len(bad), "dry_run": dry_run}


def bulk_approve_html(res: dict) -> str:
    action = "пройшли б фільтри" if res["dry_run"] else "затверджено"
    lines = [
        "🤖 <b>Пакетне затвердження AI-описів</b>",
        "",
        f"Було в черзі: <b>{res['total']}</b>",
        f"✅ Якісних ({action}): <b>{res['approved']}</b>",
        f"⚠️ Лишилось на ручну перевірку: <b>{res['left']}</b>",
    ]
    if not res["dry_run"]:
        lines += ["", "Описи підуть на сайт при наступному повному циклі синхронізації."]
    return "\n".join(lines)


# ────────────────────────── ПЕРЕВІРКА СИСТЕМИ ──────────────────────────

def health_check() -> str:
    env = _env()
    base = _base_url(env)
    lines = ["🩺 <b>ПЕРЕВІРКА СИСТЕМИ</b>", ""]

    # 1. сайт
    try:
        r = requests.get(base + "/", timeout=20, verify=False,
                         headers={"User-Agent": "Mozilla/5.0"})
        lines.append(f"{'✅' if r.status_code == 200 else '⚠️'} Сайт: HTTP {r.status_code}")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"❌ Сайт недоступний: {str(exc)[:60]}")

    # 2. база УкрСкладу
    try:
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        from ukrsklad import LIVE_DB
        if LIVE_DB.exists():
            mb = LIVE_DB.stat().st_size / 1024 / 1024
            age_h = (time.time() - LIVE_DB.stat().st_mtime) / 3600
            mark = "✅" if age_h < 48 else "⚠️"
            lines.append(f"{mark} База УкрСкладу: {mb:.0f} МБ, оновлена {age_h:.0f} год тому")
            lines.append(f"     <code>{LIVE_DB}</code>")
        else:
            lines.append(f"❌ База УкрСкладу не знайдена: {LIVE_DB}")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"❌ Модуль УкрСкладу: {str(exc)[:60]}")

    # 3. локальні дані
    products = ROOT / "data" / "products.json"
    if products.exists():
        age_h = (time.time() - products.stat().st_mtime) / 3600
        mark = "✅" if age_h < 48 else "⚠️"
        lines.append(f"{mark} Дані каталогу: оновлені {age_h:.0f} год тому")
    else:
        lines.append("❌ products.json відсутній")

    # 4. доступ до адмінки
    lines.append("✅ Логін Horoshop заданий" if env.get("HOROSHOP_LOGIN") else "❌ Немає HOROSHOP_LOGIN у .env")
    lines.append("✅ Токен бота заданий" if env.get("TELEGRAM_BOT_TOKEN") else "❌ Немає TELEGRAM_BOT_TOKEN")

    # 5. місце на диску
    try:
        usage = shutil.disk_usage(str(ROOT))
        free_gb = usage.free / 1024 ** 3
        mark = "✅" if free_gb > 5 else "⚠️"
        lines.append(f"{mark} Вільно на диску: {free_gb:.1f} ГБ")
    except Exception:
        pass

    # 6. останній повний цикл
    logs = sorted((ROOT / "logs").glob("pipeline_*.log"),
                  key=lambda p: p.stat().st_mtime, reverse=True) if (ROOT / "logs").is_dir() else []
    if logs:
        age_h = (time.time() - logs[0].stat().st_mtime) / 3600
        try:
            status = json.loads(logs[0].read_text(encoding="utf-8")).get("status", "?")
        except Exception:
            status = "?"
        mark = "✅" if status == "ok" and age_h < 48 else "⚠️"
        lines.append(f"{mark} Останній повний цикл: {age_h:.0f} год тому ({status})")
    else:
        lines.append("⚠️ Повний цикл ще не запускався")

    return "\n".join(lines)


# ────────────────────────── ТОВАРИ ──────────────────────────

def product_card_html(article: str) -> str:
    """Картка товару за артикулом."""
    import sys
    sys.path.insert(0, str(ROOT / "src" / "telegram_bot"))
    try:
        import backend as bk
        d = bk.product_detail(str(article).strip())
    except Exception as exc:  # noqa: BLE001
        return f"⚠️ Помилка пошуку: {exc}"
    if not d:
        return f"❌ Товар з артикулом <code>{article}</code> не знайдено."

    base = _base_url(_env())
    lines = [
        f"📦 <b>{d.get('title', '?')}</b>",
        "",
        f"🔖 Артикул: <code>{d.get('article')}</code>",
        f"💰 Ціна: <b>{d.get('price', 0):g} грн</b>",
        f"📊 Залишок: <b>{d.get('qty', 0)}</b>",
    ]
    if d.get("brand"):
        lines.append(f"🏷 Бренд: {d['brand']}")
    if d.get("category"):
        lines.append(f"📂 Категорія: {d['category']}")
    params = d.get("params") or []
    if params:
        lines.append("")
        lines.append("⚙️ Характеристики:")
        for p in params[:8]:
            lines.append(f"   • {p.get('name')}: {p.get('value')}")
    if d.get("id"):
        lines.append("")
        lines.append(f"🔗 {base}/catalog/{d['id']}/")
    return "\n".join(lines)


def lowstock_html(threshold: int = 3, limit: int = 30) -> str:
    import html as H
    bk = _backend()
    rows = bk.lowstock(threshold)[:limit]
    if not rows:
        return f"✅ Немає товарів із залишком ≤ {threshold}."
    lines = [f"⚠️ <b>Малий залишок (≤ {threshold}) — {len(rows)}:</b>", ""]
    for r in rows:
        lines.append(f"• <code>{H.escape(str(r['article']))}</code> "
                     f"{H.escape(str(r['title'] or '')[:40])} — залишилось <b>{r['qty']}</b>")
    return "\n".join(lines)


def recent_html(n: int = 12) -> str:
    import html as H
    bk = _backend()
    rows = bk.recent_products(n)
    if not rows:
        return "Немає даних про останні додані."
    lines = ["🆕 <b>Останні додані на сайт:</b>", ""]
    for r in rows:
        lines.append(f"• <code>{H.escape(str(r['article']))}</code> "
                     f"{H.escape(str(r['title'] or '')[:42])} — {r['price']} грн")
    return "\n".join(lines)


def live_count_html() -> str:
    bk = _backend()
    n = bk.live_product_count()
    return f"🌐 На сайті зараз: <b>{n}</b> товарів" if n else "⚠️ Не вдалося отримати кількість із сайту."


def set_field_html(text: str, field: str) -> str:
    """text = 'артикул значення'. field: 'price' | 'quantity'."""
    import html as H
    parts = text.split()
    if len(parts) < 2:
        return "Формат: <code>артикул значення</code>, напр. <code>1497 550</code>"
    bk = _backend()
    ok, m = bk.set_field(parts[0], field, parts[1])
    return ("✅ " if ok else "❌ ") + H.escape(m)


def _backend():
    import sys
    sys.path.insert(0, str(ROOT / "src" / "telegram_bot"))
    import backend
    return backend


def search_html(query: str, limit: int = 8) -> str:
    import sys
    sys.path.insert(0, str(ROOT / "src" / "telegram_bot"))
    try:
        import backend as bk
        rows = bk.search_products(query, limit=limit)
    except Exception as exc:  # noqa: BLE001
        return f"⚠️ Помилка пошуку: {exc}"
    if not rows:
        return f"❌ Нічого не знайдено за запитом «{query}»."
    lines = [f"🔎 <b>Знайдено {len(rows)}</b> за «{query}»:", ""]
    for r in rows:
        qty = r.get("quantity", 0)
        mark = "🟢" if qty else "🔴"
        lines.append(f"{mark} <code>{r.get('article')}</code> — {(r.get('title') or '')[:44]}")
        lines.append(f"     {r.get('price', 0):g} грн · залишок {qty}")
    lines.append("")
    lines.append("Надішліть артикул, щоб побачити картку товару.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(health_check().replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", ""))
    print()
    print(photo_todo_html(5).replace("<b>", "").replace("</b>", "")
          .replace("<i>", "").replace("</i>", "").replace("<code>", "").replace("</code>", ""))
    print()
    print(search_html("WEIDA CARP", 3).replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", ""))
    print()
    print(product_card_html("227").replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", ""))
