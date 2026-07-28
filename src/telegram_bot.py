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
        from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
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
        kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="⏭ Наступний товар")],
                [KeyboardButton(text="🔄 Запустити синхронізацію")],
                [KeyboardButton(text="📥 Оновити систему та перезапустити"), KeyboardButton(text="🛑 Зупинити всі процеси")]
            ],
            resize_keyboard=True
        )
        await msg.answer(
            f"👋 Вітаю, {msg.from_user.first_name}!\n\n"
            f"Стат: {json.dumps(s, ensure_ascii=False)}",
            reply_markup=kb
        )

    @dp.message(F.text == "📊 Статистика")
    async def text_stats(msg: Message):
        await cmd_stats(msg)

    @dp.message(F.text == "⏭ Наступний товар")
    async def text_next(msg: Message):
        await cmd_next(msg)

    @dp.message(F.text == "🔄 Запустити синхронізацію")
    async def text_run_sync(msg: Message):
        if not is_admin(msg): return
        await msg.answer("⏳ Запускаю повний цикл (pipeline). Це займе 1-2 хвилини...")
        import subprocess
        try:
            py_exe = sys.executable.replace("pythonw.exe", "python.exe")
            cmd = [py_exe, str(ROOT / "src" / "run_pipeline.py")]
            res = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True)
            if res.returncode == 0:
                out_safe = res.stdout.replace("<", "&lt;").replace(">", "&gt;")[-1000:]
                await msg.answer(f"✅ Успішно завершено!\n\nОстанні рядки логу:\n<pre>{out_safe}</pre>", parse_mode="HTML")
            else:
                err_safe = res.stderr.replace("<", "&lt;").replace(">", "&gt;")[-1000:]
                await msg.answer(f"❌ Помилка!\n\n<pre>{err_safe}</pre>", parse_mode="HTML")
        except Exception as e:
            await msg.answer(f"❌ Виняток: {e}")

    @dp.message(F.text == "📥 Оновити систему та перезапустити")
    async def text_update_github(msg: Message):
        if not is_admin(msg): return
        await msg.answer("⏳ Завантажую оновлення з GitHub...")
        import subprocess
        try:
            cmd = ["git", "pull", "origin", "main"]
            res = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, cwd=str(ROOT))
            if res.returncode == 0:
                out = res.stdout.strip()
                if "Already up to date" in out:
                    await msg.answer("✅ Система вже оновлена (Already up to date).")
                else:
                    safe_out = out.replace("<", "&lt;").replace(">", "&gt;")[-500:]
                    await msg.answer(f"✅ Оновлено успішно:\n<pre>{safe_out}</pre>\n🔄 Перезапускаю бота...", parse_mode="HTML")
                    os.execv(sys.executable, [sys.executable] + sys.argv)
            else:
                safe_err = res.stderr.replace("<", "&lt;").replace(">", "&gt;")[-1000:]
                await msg.answer(f"❌ Помилка оновлення:\n<pre>{safe_err}</pre>", parse_mode="HTML")
        except Exception as e:
            await msg.answer(f"❌ Виняток: {e}")

    @dp.message(F.text == "🛑 Зупинити всі процеси")
    async def text_stop_processes(msg: Message):
        if not is_admin(msg): return
        await msg.answer("⏳ Зупиняю всі фонові процеси (крім самого бота)...")
        import subprocess
        try:
            # Kill all python processes except telegram_bot, and kill chrome
            ps_script = (
                "Get-WmiObject Win32_Process | "
                "Where-Object { $_.CommandLine -match 'python' -and $_.CommandLine -notmatch 'telegram_bot' } | "
                "Stop-Process -Force -ErrorAction SilentlyContinue; "
                "Get-Process chrome, chromedriver -ErrorAction SilentlyContinue | Stop-Process -Force"
            )
            res = await asyncio.to_thread(subprocess.run, ["powershell", "-Command", ps_script], capture_output=True, text=True)
            await msg.answer("✅ Усі фонові процеси синхронізації та браузери успішно зупинено!")
        except Exception as e:
            await msg.answer(f"❌ Помилка при зупинці: {e}")

    @dp.message(Command("stats"))
    async def cmd_stats(msg):
        if not is_admin(msg): return
        s_json = json.dumps(stats(), ensure_ascii=False, indent=2)
        await msg.answer(f"<pre>{s_json}</pre>", parse_mode="HTML")

    @dp.message(Command("pending"))
    async def cmd_pending(msg):
        if not is_admin(msg): return
        rows = list_pending()
        text = "Чекає модерації:\n" + "\n".join(f"• {r['parent_key']} — {r['display_name']}" for r in rows)
        await msg.answer(text or "Нічого нового.")

    def get_inline_kb(parent_key: str):
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Approve", callback_data=f"approve:{parent_key}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"reject:{parent_key}"),
            ],
            [
                InlineKeyboardButton(text="🔄 Regen", callback_data=f"regen:{parent_key}")
            ]
        ])

    @dp.message(Command("next"))
    async def cmd_next(msg):
        if not is_admin(msg): return
        rows = list_pending(limit=1)
        if not rows:
            return await msg.answer("Нічого на модерації.")
        pk = rows[0]["parent_key"]
        await msg.answer(format_model_card(pk), reply_markup=get_inline_kb(pk))

    async def parse_arg(msg) -> str:
        parts = msg.text.split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else ""

    @dp.message(Command("show"))
    async def cmd_show(msg):
        if not is_admin(msg): return
        pk = await parse_arg(msg)
        await msg.answer(format_model_card(pk), reply_markup=get_inline_kb(pk))

    @dp.callback_query(F.data.startswith("approve:"))
    async def cb_approve(call: CallbackQuery):
        if not is_admin(call): return
        pk = call.data.split(":")[1]
        ok = set_status(pk, "approved")
        await call.message.edit_text(call.message.text + "\n\n✅ Затверджено!")
        await call.answer("Approved!")
        await cmd_next(call.message)

    @dp.callback_query(F.data.startswith("reject:"))
    async def cb_reject(call: CallbackQuery):
        if not is_admin(call): return
        pk = call.data.split(":")[1]
        ok = set_status(pk, "rejected")
        await call.message.edit_text(call.message.text + "\n\n❌ Відхилено!")
        await call.answer("Rejected!")
        await cmd_next(call.message)

    @dp.callback_query(F.data.startswith("regen:"))
    async def cb_regen(call: CallbackQuery):
        if not is_admin(call): return
        pk = call.data.split(":")[1]
        ok = set_status(pk, "draft")
        await call.message.edit_text(call.message.text + "\n\n🔄 Відправлено на перегенерацію!")
        await call.answer("Regen!")
        await cmd_next(call.message)

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
