"""
Telegram-бот для модерації AI-згенерованого контенту.

Стани моделі:
  draft     — нова, AI ще не пройшов
  ai_draft  — AI згенерував, чекає на модератора
  approved  — Марина схвалила, йде у фіди
  rejected  — Марина відхилила, треба регенерувати або редагувати

Команди:
  /start                  — привітання + статистика
  /pending                — показати скільки на модерації
  /next                   — показати наступну ai_draft модель: title, опис, params, фото
  /show <parent_key>      — показати конкретну
  /approve <parent_key>   — позначити approved
  /reject <parent_key>    — позначити rejected (опис залишається, статус міняється)
  /regen <parent_key>     — поставити status='draft' щоб AI перегенерував наступним прогоном
  /stats                  — загальна статистика

Запуск:
  Реальний:    python src/telegram_bot.py
               (потрібен TELEGRAM_BOT_TOKEN та TELEGRAM_ADMIN_IDS у .env)
  Симуляція:   python src/telegram_bot.py --simulate
               (CLI-інтерфейс без живого Telegram, для smoke-тесту логіки)

Залежність:  pip install aiogram==3.13.1
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(r"D:\FISH\fish-sync")
META_DB = ROOT / "data" / "meta_store.sqlite"
load_dotenv(ROOT / ".env")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_IDS = {int(x) for x in os.environ.get("TELEGRAM_ADMIN_IDS", "").split(",") if x.strip().isdigit()}


# ─────────── Бізнес-логіка (працює і в боті, і в симуляторі) ───────────

def db():
    conn = sqlite3.connect(META_DB)
    conn.row_factory = sqlite3.Row
    return conn


def stats() -> dict:
    with db() as conn:
        rows = conn.execute("SELECT status, COUNT(*) AS n FROM models GROUP BY status").fetchall()
    out = {r["status"]: r["n"] for r in rows}
    out["total"] = sum(out.values())
    return out


def list_pending(limit: int = 10) -> list[sqlite3.Row]:
    with db() as conn:
        return conn.execute(
            "SELECT parent_key, display_name FROM models WHERE status = 'ai_draft' ORDER BY updated_at LIMIT ?",
            (limit,),
        ).fetchall()


def get_model(parent_key: str) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute("SELECT * FROM models WHERE parent_key = ?", (parent_key,)).fetchone()


def get_variants(parent_key: str) -> list[sqlite3.Row]:
    with db() as conn:
        return conn.execute(
            "SELECT * FROM variants WHERE parent_key = ? ORDER BY kod", (parent_key,)
        ).fetchall()


def set_status(parent_key: str, status: str) -> bool:
    assert status in ("draft", "ai_draft", "approved", "rejected")
    with db() as conn:
        cur = conn.execute(
            "UPDATE models SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE parent_key = ?",
            (status, parent_key),
        )
        conn.commit()
        return cur.rowcount > 0


def format_model_card(parent_key: str) -> str:
    m = get_model(parent_key)
    if not m:
        return f"❌ Не знайдено: {parent_key}"
    variants = get_variants(parent_key)
    params = json.loads(m["common_params_json"] or "{}")
    desc = (m["description_html"] or "").replace("<p>", "").replace("</p>", "\n").replace("<ul>", "").replace("</ul>", "").replace("<li>", "• ").replace("</li>", "\n")[:1500]
    pictures = []
    for v in variants:
        pictures.extend(json.loads(v["pictures_json"] or "[]"))

    lines = [
        f"📦 {m['display_name']}",
        f"🔑 {parent_key}",
        f"📊 Статус: {m['status']}  |  Варіантів: {len(variants)}  |  Фото: {len(pictures)}",
        "",
        f"🏷 SEO: {m['seo_title']}",
        f"📝 Meta: {m['seo_meta']}",
        "",
        "⚙ Характеристики:",
    ]
    for k, v in params.items():
        lines.append(f"  • {k}: {v}")
    lines.append("")
    lines.append("📄 Опис:")
    lines.append(desc)
    lines.append("")
    lines.append("📦 Варіанти:")
    for v in variants:
        attrs = []
        if v["test_min"] is not None:
            attrs.append(f"тест {v['test_min']:g}-{v['test_max']:g}г")
        if v["length_m"]:
            attrs.append(f"{v['length_m']:g}м")
        if v["action"]:
            attrs.append(v["action"])
        lines.append(f"  · [{v['kod']}] {' '.join(attrs) or v['name_raw']}")
    lines.append("")
    lines.append(f"➡ /approve {parent_key}")
    lines.append(f"➡ /reject {parent_key}")
    lines.append(f"➡ /regen {parent_key}")
    return "\n".join(lines)


# ─────────── Симулятор (CLI без Telegram) ───────────

def simulate() -> None:
    print("=== TELEGRAM BOT SIMULATOR ===")
    print("Команди як у боті, без префіксу '/'. quit для виходу.")
    print(f"Stats: {stats()}\n")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line or line in ("quit", "exit"):
            break
        parts = line.split(maxsplit=1)
        cmd = parts[0].lstrip("/")
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "stats":
            print(json.dumps(stats(), ensure_ascii=False, indent=2))
        elif cmd == "pending":
            rows = list_pending()
            print(f"AI drafts pending: {len(rows)}")
            for r in rows:
                print(f"  · {r['parent_key']:50} — {r['display_name']}")
        elif cmd == "next":
            rows = list_pending(limit=1)
            if rows:
                print(format_model_card(rows[0]["parent_key"]))
            else:
                print("Нічого на модерації.")
        elif cmd == "show":
            print(format_model_card(arg))
        elif cmd == "approve":
            ok = set_status(arg, "approved")
            print("✅ approved" if ok else "❌ not found")
        elif cmd == "reject":
            ok = set_status(arg, "rejected")
            print("✅ rejected" if ok else "❌ not found")
        elif cmd == "regen":
            ok = set_status(arg, "draft")
            print("✅ marked for re-generation" if ok else "❌ not found")
        elif cmd == "help":
            print("Команди: stats, pending, next, show <pk>, approve <pk>, reject <pk>, regen <pk>")
        else:
            print(f"Unknown: {cmd}. Спробуй: help")


# ─────────── Real bot (Aiogram 3) ───────────

async def run_real_bot() -> None:
    if not BOT_TOKEN:
        sys.exit("TELEGRAM_BOT_TOKEN not set in .env")
    try:
        from aiogram import Bot, Dispatcher, F
        from aiogram.filters import CommandStart, Command
        from aiogram.types import Message
    except ImportError:
        sys.exit("pip install aiogram==3.13.1")

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    def is_admin(msg) -> bool:
        return not ADMIN_IDS or msg.from_user.id in ADMIN_IDS

    @dp.message(CommandStart())
    async def cmd_start(msg):
        if not is_admin(msg):
            return await msg.answer("⛔ Доступ заборонено")
        s = stats()
        await msg.answer(
            f"👋 Вітаю, {msg.from_user.first_name}!\n\n"
            f"Стат: {json.dumps(s, ensure_ascii=False)}\n\n"
            "Команди: /pending /next /show /approve /reject /regen /stats"
        )

    @dp.message(Command("stats"))
    async def cmd_stats(msg):
        if not is_admin(msg): return
        await msg.answer(f"```\n{json.dumps(stats(), ensure_ascii=False, indent=2)}\n```", parse_mode="MarkdownV2")

    @dp.message(Command("pending"))
    async def cmd_pending(msg):
        if not is_admin(msg): return
        rows = list_pending()
        text = "Чекає модерації:\n" + "\n".join(f"• {r['parent_key']} — {r['display_name']}" for r in rows)
        await msg.answer(text or "Нічого нового.")

    @dp.message(Command("next"))
    async def cmd_next(msg):
        if not is_admin(msg): return
        rows = list_pending(limit=1)
        if not rows:
            return await msg.answer("Нічого на модерації.")
        await msg.answer(format_model_card(rows[0]["parent_key"]))

    async def parse_arg(msg) -> str:
        parts = msg.text.split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else ""

    @dp.message(Command("show"))
    async def cmd_show(msg):
        if not is_admin(msg): return
        pk = await parse_arg(msg)
        await msg.answer(format_model_card(pk))

    @dp.message(Command("approve"))
    async def cmd_approve(msg):
        if not is_admin(msg): return
        pk = await parse_arg(msg)
        ok = set_status(pk, "approved")
        await msg.answer("✅ approved" if ok else "❌ not found")

    @dp.message(Command("reject"))
    async def cmd_reject(msg):
        if not is_admin(msg): return
        pk = await parse_arg(msg)
        ok = set_status(pk, "rejected")
        await msg.answer("✅ rejected" if ok else "❌ not found")

    @dp.message(Command("regen"))
    async def cmd_regen(msg):
        if not is_admin(msg): return
        pk = await parse_arg(msg)
        ok = set_status(pk, "draft")
        await msg.answer("✅ marked for re-generation" if ok else "❌ not found")

    print("Bot started, polling...")
    await dp.start_polling(bot)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulate", action="store_true")
    args = ap.parse_args()
    if args.simulate:
        simulate()
    else:
        asyncio.run(run_real_bot())


if __name__ == "__main__":
    main()
