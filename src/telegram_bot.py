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
# Технічне меню («⚙️ Ще»): якщо TELEGRAM_TECH_IDS заданий — лише ці ID бачать
# небезпечні кнопки (синк, оновлення, стоп). Порожній = усі адміни.
TECH_IDS = {int(x) for x in os.environ.get("TELEGRAM_TECH_IDS", "").split(",") if x.strip().isdigit()}


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

    def is_tech(msg) -> bool:
        return is_admin(msg) and (not TECH_IDS or msg.from_user.id in TECH_IDS)

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
            [KeyboardButton(text="⚠️ Закінчилось з топу"), KeyboardButton(text="⚠️ Малий залишок")],
            [KeyboardButton(text="🆕 Останні додані"), KeyboardButton(text="🌐 На сайті")],
            [KeyboardButton(text="✏️ Змінити ціну"), KeyboardButton(text="✏️ Змінити залишок")],
            [KeyboardButton(text="🤖 AI-описи"), KeyboardButton(text="🔄 Синхронізація")],
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
            "🛒 <b>Замовлення</b> — замовлення з сайту за 7 днів (списання зі складу — автоматичне)\n"
            "🔎 <b>Знайти товар</b> — пошук за назвою; надішліть артикул — покаже картку\n"
            "📸 <b>Що фоткати</b> — черга товарів без фото\n"
            "   ↳ надішліть фото (можна альбомом), у підпис — артикул, і вони підуть на сайт\n"
            "📊 <b>Статистика</b> — стан магазину\n\n"
            "⚙️ <b>Ще</b> — технічне: перевірка системи, малий залишок, останні додані, "
            "живий лічильник, зміна ціни/залишку, AI-описи (в т.ч. пакетне затвердження), "
            "синхронізація, оновлення бота\n\n"
            "Автоматично приходять: нові замовлення (кожні 10 хв), алерт коли топ-товар "
            "у нулі, алерт якщо синк не працює &gt;24 год, тижневий звіт щопонеділка.\n\n"
            "Команди: /start /help /stats /next /pending",
            parse_mode="HTML")

    @dp.message(F.text == "⚙️ Ще")
    async def more_menu(msg: Message):
        if not is_tech(msg):
            if is_admin(msg):
                await msg.answer("⚙️ Технічне меню доступне лише адміністратору системи.")
            return
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
        await msg.answer("⏳ Читаю замовлення з сайту (до хвилини)…")
        import subprocess
        try:
            py = sys.executable.replace("pythonw.exe", "python.exe")
            # --list: лише показати, БЕЗ сповіщень і без запису в журнал
            res = await asyncio.to_thread(
                subprocess.run, [py, str(ROOT / "src" / "notify_new_orders.py"),
                                 "--list", "--days", "7"],
                capture_output=True, text=True, timeout=300)
            out = (res.stdout or "").strip()
            if "===ORDER===" not in out:
                await msg.answer("📭 Замовлень за 7 днів немає.\n\n"
                                 "<i>Сповіщення про нові приходять автоматично кожні 10 хв.</i>",
                                 parse_mode="HTML")
                return
            cards = [c.strip() for c in out.split("===ORDER===") if c.strip().startswith("🎣")]
            await msg.answer(f"🛒 <b>Замовлення за 7 днів: {len(cards)}</b>", parse_mode="HTML")
            for card in cards[:10]:
                await safe_answer(msg, card, parse_mode="HTML")
            if len(cards) > 10:
                await msg.answer(f"… і ще {len(cards) - 10} (див. адмінку).")
            await msg.answer("<i>Списання зі складу відбувається автоматично щогодини "
                             "(або кнопкою 🔄 Синхронізація → Замовлення).</i>", parse_mode="HTML")
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

    # Буфер альбомів: media_group_id -> {"photos": [...], "article": str, "task": Task}
    # Telegram шле альбом окремими повідомленнями (підпис лише в одного) —
    # збираємо їх ~3 с і заливаємо разом, інакше губились усі фото крім останнього.
    albums: dict[str, dict] = {}

    async def _download_incoming(msg: Message) -> str | None:
        """Фото або зображення-документ → локальний файл. None = не зображення."""
        tmp_dir = ROOT / "tmp" / "bot_incoming"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        if msg.photo:
            photo = msg.photo[-1]                  # найбільша якість
            dest = tmp_dir / f"{photo.file_unique_id}.jpg"
            await bot.download(photo, destination=dest)
            return str(dest)
        doc = msg.document
        if doc and (doc.mime_type or "").startswith("image/"):
            suffix = Path(doc.file_name or "img.jpg").suffix or ".jpg"
            dest = tmp_dir / f"{doc.file_unique_id}{suffix}"
            await bot.download(doc, destination=dest)
            return str(dest)
        return None

    async def _flush_album(mgid: str, msg: Message):
        await asyncio.sleep(3)                     # чекаємо решту фото альбому
        entry = albums.pop(mgid, None)
        if not entry:
            return
        article = entry.get("article") or ""
        photos = entry["photos"]
        if not article:
            state[msg.from_user.id] = {"mode": "await_article", "photos": photos}
            return await msg.answer(
                f"📸 Отримано {len(photos)} фото. Надішліть <b>артикул</b> товару, "
                "щоб я залив їх на сайт.\n<i>(або натисніть ⬅️ Назад щоб скасувати)</i>",
                parse_mode="HTML")
        await do_upload_photos(msg, article, photos)

    @dp.message(F.photo)
    @dp.message(F.document)
    async def handle_photo(msg: Message):
        if not is_admin(msg): return
        path = await _download_incoming(msg)
        if path is None:
            return await msg.answer("Я приймаю лише зображення (фото або файл-картинку).")
        article = (msg.caption or "").strip().split()[0] if msg.caption else ""

        if msg.media_group_id:                     # альбом — буферизуємо
            mgid = str(msg.media_group_id)
            entry = albums.setdefault(mgid, {"photos": [], "article": ""})
            entry["photos"].append(path)
            if article:
                entry["article"] = article
            if entry.get("task"):
                entry["task"].cancel()
            entry["task"] = asyncio.create_task(_flush_album(mgid, msg))
            return

        if not article:
            state[msg.from_user.id] = {"mode": "await_article", "photos": [path]}
            return await msg.answer(
                "📸 Фото отримано. Надішліть <b>артикул</b> товару, "
                "щоб я залив його на сайт.\n<i>(або натисніть ⬅️ Назад щоб скасувати)</i>",
                parse_mode="HTML")
        await do_upload_photos(msg, article, [path])

    async def do_upload_photos(msg: Message, article: str, paths: list[str]):
        n = len(paths)
        await msg.answer(f"⏳ Заливаю {n} фото на товар <code>{article}</code>…", parse_mode="HTML")
        ok_count, last_err = 0, ""
        try:
            import bot_actions
            for i, path in enumerate(paths):
                try:
                    ready = await asyncio.to_thread(bot_actions.prepare_photo, path)
                except Exception:
                    ready = path                   # ресайз не критичний — заливаємо як є
                # перше фото замінює галерею (прибирає заглушку), решта — додаються
                ok, text = await asyncio.to_thread(
                    bot_actions.upload_photo_for_article, article, ready, i == 0)
                if ok:
                    ok_count += 1
                else:
                    last_err = text
        except Exception as exc:
            last_err = f"Помилка: {exc}"
        state.pop(msg.from_user.id, None)
        if ok_count:
            card = ""
            try:
                import bot_actions as ba
                card = "\n\n" + ba.product_card_html(article)
            except Exception:
                pass
            extra = f"\n⚠️ Не залилось: {n - ok_count} ({last_err})" if ok_count < n else ""
            await safe_answer(msg, f"✅ Залито {ok_count} з {n} фото на товар "
                                   f"<code>{article}</code>.{extra}{card}", parse_mode="HTML")
        else:
            await msg.answer(f"❌ {last_err or 'Не вдалося залити фото.'}")

    # ─────────── пошук товару ───────────

    @dp.message(F.text == "🔎 Знайти товар")
    async def text_search_prompt(msg: Message):
        if not is_admin(msg): return
        state[msg.from_user.id] = {"mode": "await_query"}
        await msg.answer("🔎 Надішліть назву або артикул товару.")

    # ─────────── каталог: залишки / останні / live-лічильник ───────────

    async def _bot_action_answer(msg: Message, fn_name: str, *args):
        """Виклик функції bot_actions у потоці + відповідь HTML."""
        try:
            import bot_actions
            out = await asyncio.to_thread(getattr(bot_actions, fn_name), *args)
        except Exception as exc:
            out = f"❌ Помилка: {exc}"
        await safe_answer(msg, out, parse_mode="HTML")

    @dp.message(F.text == "⚠️ Малий залишок")
    async def text_lowstock(msg: Message):
        if not is_admin(msg): return
        await msg.answer("⏳ Рахую…")
        await _bot_action_answer(msg, "lowstock_html", 3)

    @dp.message(F.text == "🆕 Останні додані")
    async def text_recent(msg: Message):
        if not is_admin(msg): return
        await _bot_action_answer(msg, "recent_html", 12)

    @dp.message(F.text == "🌐 На сайті")
    async def text_live_count(msg: Message):
        if not is_admin(msg): return
        await msg.answer("⏳ Питаю сайт…")
        await _bot_action_answer(msg, "live_count_html")

    # ─────────── зміна ціни / залишку ───────────

    @dp.message(F.text == "✏️ Змінити ціну")
    async def text_setprice(msg: Message):
        if not is_tech(msg): return
        state[msg.from_user.id] = {"mode": "await_setprice"}
        await msg.answer("✏️ Надішліть: <code>артикул нова_ціна</code>\n"
                         "напр. <code>1497 550</code>", parse_mode="HTML")

    @dp.message(F.text == "✏️ Змінити залишок")
    async def text_setstock(msg: Message):
        if not is_tech(msg): return
        state[msg.from_user.id] = {"mode": "await_setstock"}
        await msg.answer("✏️ Надішліть: <code>артикул кількість</code>\n"
                         "напр. <code>1497 10</code>", parse_mode="HTML")

    # ─────────── AI-описи (модерація) ───────────

    @dp.message(F.text == "🤖 AI-описи")
    async def text_ai_menu(msg: Message):
        if not is_admin(msg): return
        s = stats()
        pending = s.get("ai_draft", 0)
        if not pending:
            return await msg.answer("✅ Черга AI-описів порожня.")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Перевіряти по одному", callback_data="do:ai_next")],
            [InlineKeyboardButton(text=f"⚡ Затвердити всі якісні ({pending} у черзі)",
                                  callback_data="do:ai_bulk_ask")],
        ])
        await msg.answer(
            f"🤖 <b>AI-описи: {pending} чекають перевірки</b>\n\n"
            "Поки опис не затверджено — на сайті його НЕМАЄ (товар без опису).\n\n"
            "📝 <i>По одному</i> — читати кожен і тапати ✅/❌\n"
            "⚡ <i>Всі якісні</i> — автоматично затвердити ті, що проходять фільтри "
            "якості (довжина, шаблонність, сміттєвий текст); сумнівні лишаться на ручну перевірку",
            reply_markup=kb, parse_mode="HTML")

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

        if action == "ai_next":
            return await send_next_card(msg)

        if action == "ai_bulk_ask":
            try:
                import bot_actions
                res = await asyncio.to_thread(bot_actions.bulk_approve_stats)
            except Exception as exc:
                return await msg.answer(f"❌ Помилка: {exc}")
            return await msg.answer(
                bot_actions.bulk_approve_html(res) +
                "\n\nЗатвердити? Це лише статус у локальній базі — "
                "на сайт піде при наступному повному циклі.",
                reply_markup=confirm_kb("ai_bulk"), parse_mode="HTML")

        if action == "ai_bulk":
            await msg.answer("⏳ Затверджую…")
            try:
                import bot_actions
                res = await asyncio.to_thread(bot_actions.bulk_approve_ai)
                return await msg.answer(bot_actions.bulk_approve_html(res), parse_mode="HTML")
            except Exception as exc:
                return await msg.answer(f"❌ Помилка: {exc}")

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
                py = sys.executable.replace("pythonw.exe", "python.exe")
                subprocess.Popen([py] + sys.argv, creationflags=0x00000008)
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

        # чекаємо артикул для щойно надісланих фото
        if st.get("mode") == "await_article" and st.get("photos"):
            return await do_upload_photos(msg, text.split()[0], st["photos"])

        # чекаємо «артикул значення» для зміни ціни/залишку
        if st.get("mode") in ("await_setprice", "await_setstock"):
            field = "price" if st["mode"] == "await_setprice" else "quantity"
            state.pop(msg.from_user.id, None)
            await msg.answer("⏳ Зберігаю…")
            try:
                import bot_actions
                out = await asyncio.to_thread(bot_actions.set_field_html, text, field)
            except Exception as exc:
                out = f"❌ Помилка: {exc}"
            return await safe_answer(msg, out, parse_mode="HTML")

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
    delay = 30
    while True:
        try:
            await dp.start_polling(bot)
            delay = 30                             # нормальне завершення — скинути backoff
        except Exception as e:
            print(f"Polling error: {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay)
            delay = min(delay * 2, 900)            # 30с → 1хв → … → макс 15хв


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
