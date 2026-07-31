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

ROOT = Path(__file__).resolve().parent.parent   # не хардкодимо D:\FISH — працює з будь-якої теки
META_DB = ROOT / "data" / "meta_store.sqlite"
load_dotenv(ROOT / ".env")

sys.path.insert(0, str(ROOT / "src"))
try:
    import bot_dashboard  # реальна бізнес-статистика
except Exception:  # pragma: no cover
    bot_dashboard = None

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


def build_stats_text() -> str:
    """Головна статистика: реальні бізнес-метрики + черга модерації AI."""
    parts = []
    if bot_dashboard is not None:
        try:
            parts.append(bot_dashboard.dashboard_html())
        except Exception as exc:  # не валимо бота через статистику
            parts.append(f"⚠️ Дашборд недоступний: {exc}")
    s = stats()
    parts.append(
        "\n🤖 <b>Черга AI-описів</b>\n"
        f"   Чекають перевірки: <b>{s.get('ai_draft', 0)}</b>\n"
        f"   Ще без опису: {s.get('draft', 0)}\n"
        f"   Затверджено: {s.get('approved', 0)} · відхилено: {s.get('rejected', 0)}"
    )
    return "\n".join(parts)


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
        from aiogram.types import (Message, ReplyKeyboardMarkup, KeyboardButton,
                                   InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery)
    except ImportError:
        sys.exit("pip install -r requirements.txt  (потрібен aiogram==3.13.1)")

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    # Проста памʼять діалогу: {user_id: {"mode": ..., "photo": ...}}
    state: dict[int, dict] = {}

    def is_admin(msg) -> bool:
        return not ADMIN_IDS or msg.from_user.id in ADMIN_IDS

    # ─────────── клавіатури ───────────

    MAIN_KB = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Замовлення"), KeyboardButton(text="🔎 Знайти товар")],
            [KeyboardButton(text="📸 Що фоткати"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="⚙️ Ще")],
        ],
        resize_keyboard=True,
    )
    MORE_KB = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🩺 Перевірка системи"), KeyboardButton(text="🏆 Топ продажів")],
            [KeyboardButton(text="⚠️ Закінчилось з топу"), KeyboardButton(text="🤖 AI-описи")],
            [KeyboardButton(text="🔄 Синхронізація")],
            [KeyboardButton(text="📥 Оновити бота"), KeyboardButton(text="🛑 Стоп процеси")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
    )

    def confirm_kb(action: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Так", callback_data=f"do:{action}"),
            InlineKeyboardButton(text="✖️ Скасувати", callback_data="do:cancel"),
        ]])

    async def safe_answer(msg, text: str, **kw):
        """Telegram не приймає >4096 символів."""
        for i in range(0, len(text), 3900):
            await msg.answer(text[i:i + 3900], **kw)

    # ─────────── старт / довідка ───────────

    @dp.message(CommandStart())
    async def cmd_start(msg: Message):
        if not is_admin(msg):
            return await msg.answer("⛔ Доступ заборонено")
        state.pop(msg.from_user.id, None)
        await safe_answer(msg, f"👋 Вітаю, {msg.from_user.first_name}!\n\n" + build_stats_text(),
                          reply_markup=MAIN_KB, parse_mode="HTML")

    @dp.message(Command("help"))
    async def cmd_help(msg: Message):
        if not is_admin(msg): return
        await msg.answer(
            "<b>Що вміє бот</b>\n\n"
            "🛒 <b>Замовлення</b> — нові замовлення з сайту\n"
            "🔎 <b>Знайти товар</b> — пошук за назвою; надішліть артикул — покаже картку\n"
            "📸 <b>Що фоткати</b> — черга товарів без фото\n"
            "   ↳ надішліть фото, а в підпис — артикул, і воно одразу піде на сайт\n"
            "📊 <b>Статистика</b> — стан магазину\n\n"
            "⚙️ <b>Ще</b> — технічне: перевірка системи, синхронізація, оновлення бота\n\n"
            "Команди: /start /help /stats /next /pending",
            parse_mode="HTML")

    @dp.message(F.text == "⚙️ Ще")
    async def more_menu(msg: Message):
        if not is_admin(msg): return
        await msg.answer("⚙️ Технічне меню", reply_markup=MORE_KB)

    @dp.message(F.text == "⬅️ Назад")
    async def back_menu(msg: Message):
        if not is_admin(msg): return
        state.pop(msg.from_user.id, None)
        await msg.answer("Головне меню", reply_markup=MAIN_KB)

    # ─────────── статистика ───────────

    @dp.message(Command("stats"))
    @dp.message(F.text == "📊 Статистика")
    async def cmd_stats(msg: Message):
        if not is_admin(msg): return
        await safe_answer(msg, build_stats_text(), parse_mode="HTML")

    @dp.message(F.text == "🏆 Топ продажів")
    async def text_top_sales(msg: Message):
        if not is_admin(msg): return
        if bot_dashboard is None:
            return await msg.answer("Модуль статистики недоступний.")
        await safe_answer(msg, bot_dashboard.top_sellers_html(7), parse_mode="HTML")

    @dp.message(F.text == "⚠️ Закінчилось з топу")
    async def text_stale_top(msg: Message):
        if not is_admin(msg): return
        if bot_dashboard is None:
            return await msg.answer("Модуль статистики недоступний.")
        await safe_answer(msg, bot_dashboard.stale_top_html(10), parse_mode="HTML")

    @dp.message(F.text == "🩺 Перевірка системи")
    async def text_health(msg: Message):
        if not is_admin(msg): return
        await msg.answer("⏳ Перевіряю…")
        try:
            import bot_actions
            res = await asyncio.to_thread(bot_actions.health_check)
        except Exception as exc:
            res = f"❌ Помилка перевірки: {exc}"
        await safe_answer(msg, res, parse_mode="HTML")

    # ─────────── замовлення ───────────

    @dp.message(F.text == "🛒 Замовлення")
    async def text_orders(msg: Message):
        if not is_admin(msg): return
        await msg.answer("⏳ Перевіряю нові замовлення на сайті (до хвилини)…")
        import subprocess
        try:
            py = sys.executable.replace("pythonw.exe", "python.exe")
            res = await asyncio.to_thread(
                subprocess.run, [py, str(ROOT / "src" / "notify_new_orders.py"), "--days", "7"],
                capture_output=True, text=True, timeout=300)
            out = (res.stdout or res.stderr or "").strip()
            tail = out.replace("<", "&lt;").replace(">", "&gt;")[-1500:]
            if "Нових замовлень немає" in out:
                await msg.answer("📭 Нових замовлень немає.\n\n"
                                 "<i>Сповіщення про нові приходять автоматично кожні 10 хв.</i>",
                                 parse_mode="HTML")
            else:
                await safe_answer(msg, f"🛒 <b>Замовлення</b>\n<pre>{tail}</pre>", parse_mode="HTML")
        except Exception as exc:
            await msg.answer(f"❌ Помилка: {exc}")

    # ─────────── фото ───────────

    @dp.message(F.text == "📸 Що фоткати")
    async def text_photo_todo(msg: Message):
        if not is_admin(msg): return
        try:
            import bot_actions
            await safe_answer(msg, bot_actions.photo_todo_html(10), parse_mode="HTML")
        except Exception as exc:
            await msg.answer(f"❌ Помилка: {exc}")

    @dp.message(F.photo)
    async def handle_photo(msg: Message):
        if not is_admin(msg): return
        article = (msg.caption or "").strip().split()[0] if msg.caption else ""
        tmp_dir = ROOT / "tmp" / "bot_incoming"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        photo = msg.photo[-1]                      # найбільша якість
        dest = tmp_dir / f"{photo.file_unique_id}.jpg"
        await bot.download(photo, destination=dest)

        if not article:
            state[msg.from_user.id] = {"mode": "await_article", "photo": str(dest)}
            return await msg.answer(
                "📸 Фото отримано. Надішліть <b>артикул</b> товару, "
                "щоб я залив його на сайт.\n<i>(або натисніть ⬅️ Назад щоб скасувати)</i>",
                parse_mode="HTML")
        await do_upload_photo(msg, article, str(dest))

    async def do_upload_photo(msg: Message, article: str, path: str):
        await msg.answer(f"⏳ Заливаю фото на товар <code>{article}</code>…", parse_mode="HTML")
        try:
            import bot_actions
            ok, text = await asyncio.to_thread(
                bot_actions.upload_photo_for_article, article, path, True)
        except Exception as exc:
            ok, text = False, f"Помилка: {exc}"
        state.pop(msg.from_user.id, None)
        if ok:
            card = ""
            try:
                import bot_actions as ba
                card = "\n\n" + ba.product_card_html(article)
            except Exception:
                pass
            await safe_answer(msg, f"✅ {text}{card}", parse_mode="HTML")
        else:
            await msg.answer(f"❌ {text}")

    # ─────────── пошук товару ───────────

    @dp.message(F.text == "🔎 Знайти товар")
    async def text_search_prompt(msg: Message):
        if not is_admin(msg): return
        state[msg.from_user.id] = {"mode": "await_query"}
        await msg.answer("🔎 Надішліть назву або артикул товару.")

    # ─────────── AI-описи (модерація) ───────────

    @dp.message(F.text == "🤖 AI-описи")
    @dp.message(Command("next"))
    async def cmd_next(msg: Message):
        if not is_admin(msg): return
        await send_next_card(msg)

    @dp.message(Command("pending"))
    async def cmd_pending(msg: Message):
        if not is_admin(msg): return
        rows = list_pending()
        text = "Чекає модерації:\n" + "\n".join(
            f"• {r['parent_key']} — {r['display_name']}" for r in rows)
        await safe_answer(msg, text or "Нічого нового.")

    def get_inline_kb(parent_key: str):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Затвердити", callback_data=f"approve:{parent_key}"),
             InlineKeyboardButton(text="❌ Відхилити", callback_data=f"reject:{parent_key}")],
            [InlineKeyboardButton(text="🔄 Перегенерувати", callback_data=f"regen:{parent_key}")],
        ])

    async def send_next_card(target) -> None:
        """Наступна картка. БЕЗ перевірки адміна — вона вже пройдена вище.
        (Раніше callback звав cmd_next(call.message), де from_user = сам бот.)"""
        rows = list_pending(limit=1)
        if not rows:
            return await target.answer("✅ Черга порожня — усе перевірено.")
        pk = rows[0]["parent_key"]
        await target.answer(format_model_card(pk), reply_markup=get_inline_kb(pk))

    @dp.message(Command("show"))
    async def cmd_show(msg: Message):
        if not is_admin(msg): return
        parts = msg.text.split(maxsplit=1)
        pk = parts[1].strip() if len(parts) > 1 else ""
        await msg.answer(format_model_card(pk), reply_markup=get_inline_kb(pk))

    @dp.callback_query(F.data.startswith(("approve:", "reject:", "regen:")))
    async def cb_moderate(call: CallbackQuery):
        if not is_admin(call): return
        action, pk = call.data.split(":", 1)
        status = {"approve": "approved", "reject": "rejected", "regen": "draft"}[action]
        label = {"approve": "✅ Затверджено", "reject": "❌ Відхилено",
                 "regen": "🔄 На перегенерацію"}[action]
        set_status(pk, status)
        try:
            await call.message.edit_text((call.message.text or "") + f"\n\n{label}")
        except Exception:
            pass
        await call.answer(label)
        await send_next_card(call.message)

    # ─────────── синхронізація ───────────

    @dp.message(F.text == "🔄 Синхронізація")
    async def text_sync_menu(msg: Message):
        if not is_admin(msg): return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 Залишки та ціни", callback_data="do:sync_stock")],
            [InlineKeyboardButton(text="🛒 Замовлення → УкрСклад", callback_data="do:sync_orders")],
            [InlineKeyboardButton(text="🔁 Повний цикл (довго)", callback_data="do:pipeline")],
        ])
        await msg.answer(
            "🔄 <b>Що синхронізувати?</b>\n\n"
            "📦 <i>Залишки та ціни</i> — швидко, найчастіше потрібне\n"
            "🛒 <i>Замовлення</i> — списати продане зі складу\n"
            "🔁 <i>Повний цикл</i> — усе разом, 1–2 хв, пише на сайт",
            reply_markup=kb, parse_mode="HTML")

    async def run_script(msg, script: str, title: str, args: list[str] | None = None):
        await msg.answer(f"⏳ {title}… Це може зайняти кілька хвилин.")
        import subprocess
        try:
            py = sys.executable.replace("pythonw.exe", "python.exe")
            cmd = [py, str(ROOT / "src" / script)] + (args or [])
            res = await asyncio.to_thread(subprocess.run, cmd,
                                          capture_output=True, text=True, timeout=1800)
            out = (res.stdout or "").strip() or (res.stderr or "").strip()
            safe = out.replace("<", "&lt;").replace(">", "&gt;")[-1200:]
            mark = "✅ Готово" if res.returncode == 0 else "❌ Помилка"
            await safe_answer(msg, f"{mark}\n<pre>{safe}</pre>", parse_mode="HTML")
        except Exception as exc:
            await msg.answer(f"❌ Виняток: {exc}")

    # ─────────── небезпечні дії (з підтвердженням) ───────────

    @dp.message(F.text == "📥 Оновити бота")
    async def text_update(msg: Message):
        if not is_admin(msg): return
        await msg.answer("📥 Завантажити оновлення з GitHub і перезапустити бота?",
                         reply_markup=confirm_kb("update"))

    @dp.message(F.text == "🛑 Стоп процеси")
    async def text_stop(msg: Message):
        if not is_admin(msg): return
        await msg.answer(
            "🛑 Зупинити фонові процеси синхронізації?\n"
            "<i>Ваш звичайний Chrome і сторонні програми не чіпатимуться.</i>",
            reply_markup=confirm_kb("stop"), parse_mode="HTML")

    @dp.callback_query(F.data.startswith("do:"))
    async def cb_do(call: CallbackQuery):
        if not is_admin(call): return
        action = call.data.split(":", 1)[1]
        await call.answer()
        msg = call.message

        if action == "cancel":
            return await msg.answer("Скасовано.")

        if action == "sync_stock":
            return await run_script(msg, "sync_stock_playwright.py", "Синхронізую залишки та ціни")
        if action == "sync_orders":
            return await run_script(msg, "sync_orders.py", "Забираю замовлення і списую зі складу")
        if action == "pipeline":
            return await run_script(msg, "run_pipeline.py", "Повний цикл синхронізації")

        if action == "stop":
            await msg.answer("⏳ Зупиняю фонові процеси…")
            import subprocess
            ps = (
                "$k=@(); "
                "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and "
                "$_.CommandLine -match 'fish-sync' -and $_.CommandLine -notmatch 'telegram_bot' } | "
                "ForEach-Object { $k += ('{0} {1}' -f $_.ProcessId,$_.Name); "
                "Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; "
                "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and "
                "$_.CommandLine -match '--headless' } | ForEach-Object { "
                "$k += ('{0} {1}' -f $_.ProcessId,$_.Name); "
                "Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; "
                "if ($k.Count -eq 0) { 'NONE' } else { $k -join \"`n\" }"
            )
            try:
                res = await asyncio.to_thread(
                    subprocess.run, ["powershell", "-NoProfile", "-Command", ps],
                    capture_output=True, text=True, timeout=120)
                out = (res.stdout or "").strip()
                if not out or out == "NONE":
                    await msg.answer("ℹ️ Активних процесів синхронізації не було.")
                else:
                    n = len([x for x in out.splitlines() if x.strip()])
                    safe = out.replace("<", "&lt;").replace(">", "&gt;")[-800:]
                    await msg.answer(f"✅ Зупинено: <b>{n}</b>\n<pre>{safe}</pre>",
                                     parse_mode="HTML")
            except Exception as exc:
                await msg.answer(f"❌ Помилка: {exc}")
            return

        if action == "update":
            await msg.answer("⏳ Завантажую оновлення з GitHub…")
            import subprocess
            try:
                res = await asyncio.to_thread(
                    subprocess.run, ["git", "pull", "origin", "main"],
                    capture_output=True, text=True, cwd=str(ROOT), timeout=300)
                out = (res.stdout or "").strip()
                if res.returncode != 0:
                    safe = (res.stderr or "").replace("<", "&lt;").replace(">", "&gt;")[-800:]
                    return await msg.answer(f"❌ Помилка оновлення:\n<pre>{safe}</pre>",
                                            parse_mode="HTML")
                if "Already up to date" in out or "Вже оновлено" in out:
                    return await msg.answer("✅ Уже остання версія.")
                safe = out.replace("<", "&lt;").replace(">", "&gt;")[-600:]
                await msg.answer(f"✅ Оновлено:\n<pre>{safe}</pre>\n🔄 Перезапускаюсь…",
                                 parse_mode="HTML")
                subprocess.Popen([sys.executable] + sys.argv, creationflags=0x00000008)
                os._exit(0)
            except Exception as exc:
                await msg.answer(f"❌ Виняток: {exc}")
            return

    # ─────────── вільний текст (пошук / артикул / очікування) ───────────

    @dp.message(F.text)
    async def free_text(msg: Message):
        if not is_admin(msg): return
        text = (msg.text or "").strip()
        st = state.get(msg.from_user.id) or {}

        # чекаємо артикул для щойно надісланого фото
        if st.get("mode") == "await_article" and st.get("photo"):
            return await do_upload_photo(msg, text.split()[0], st["photo"])

        if st.get("mode") == "await_query":
            state.pop(msg.from_user.id, None)

        try:
            import bot_actions
            # схоже на артикул — показуємо картку; інакше шукаємо
            looks_like_article = len(text) <= 16 and " " not in text
            out = (bot_actions.product_card_html(text) if looks_like_article
                   else bot_actions.search_html(text))
            if looks_like_article and out.startswith("❌"):
                out = bot_actions.search_html(text)
            await safe_answer(msg, out, parse_mode="HTML")
        except Exception as exc:
            await msg.answer(f"❌ Помилка: {exc}")

    print("Bot started, polling...")
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            print(f"Polling error: {e}. Retrying in 15 minutes...")
            await asyncio.sleep(900)


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
