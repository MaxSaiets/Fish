"""
⚠️ DEPRECATED (2026-08-03): цей бот НЕ використовується і НЕ повинен запускатись.
Основний бот — src/telegram_bot.py (aiogram, токен з .env). Увесь функціонал звідси
(пошук, картка, зміна ціни/залишку, малий залишок, останні, live-лічильник)
перенесено туди через backend.py. У config.json лежить ВІДКЛИКАНИЙ токен.
backend.py з цього пакета ЖИВИЙ — його імпортує bot_actions.py, не видаляти.

Telegram-бот керування магазином vsedliarybalky.com.ua — інтерфейс на КНОПКАХ.

Запуск:  python src/telegram_bot/bot.py
Конфіг:  src/telegram_bot/config.json  {"token": "...", "allowed_user_ids": [<твій id>]}

Можливості (усе через кнопки):
  📊 Статистика каталогу        🌐 Жива к-сть на сайті
  🆕 Останні додані             ⚠️ Малий залишок
  🔎 Пошук                      📦 Картка товару
  ✏️ Змінити ціну / залишок
  🔄 Синхр. ціни/залишки (УкрСклад → сайт)
  🧾 Забрати замовлення → списати в УкрСкладі (сайт → УкрСклад)
Нуль зовнішніх залежностей (лише requests). Long-polling.
"""
from __future__ import annotations

import html
import json
import sys
import threading
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

import backend as be  # noqa: E402

CONFIG = HERE / "config.json"
OFFSET_FILE = HERE / ".offset"


def load_config() -> dict:
    if not CONFIG.exists():
        raise SystemExit(f"Немає {CONFIG}. Скопіюй config.example.json → config.json і встав токен.")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    if not cfg.get("token") or cfg["token"].startswith("<"):
        raise SystemExit("У config.json не вказано токен від @BotFather.")
    cfg.setdefault("allowed_user_ids", [])
    return cfg


def kb(rows):
    """rows: list of list of (text, callback_data)."""
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in rows]}


MAIN_MENU = kb([
    [("📊 Статистика", "stats"), ("🌐 На сайті", "count")],
    [("🆕 Останні додані", "recent"), ("⚠️ Малий залишок", "low")],
    [("🔎 Пошук товару", "search"), ("📦 Картка товару", "product")],
    [("✏️ Змінити ціну", "setprice"), ("✏️ Змінити залишок", "setstock")],
    [("🔄 Синхр. ціни/залишки (УкрСклад→сайт)", "syncstock")],
    [("🧾 Забрати замовлення → списати склад", "syncorders")],
    [("ℹ️ Що вміє бот", "help")],
])
BACK = kb([[("‹ Меню", "menu")]])


class Bot:
    def __init__(self, cfg: dict):
        self.token = cfg["token"]
        self.allowed = set(cfg.get("allowed_user_ids") or [])
        self.api = f"https://api.telegram.org/bot{self.token}"
        self.offset = int(OFFSET_FILE.read_text()) if OFFSET_FILE.exists() else 0
        self.pending: dict[int, str] = {}   # chat_id -> очікувана дія (пошук/товар/ціна/залишок)
        self.busy: set[int] = set()         # chat_id із запущеною синхронізацією

    # ---- Telegram API ----
    def _post(self, method: str, **params):
        try:
            for k, v in list(params.items()):
                if isinstance(v, (dict, list)):
                    params[k] = json.dumps(v)
            return requests.post(f"{self.api}/{method}", data=params, timeout=60).json()
        except Exception as exc:
            print("API err", method, exc, flush=True)
            return {}

    def send(self, chat_id, text, keyboard=None):
        for i in range(0, len(text), 3800):
            self._post("sendMessage", chat_id=chat_id, text=text[i:i + 3800],
                       parse_mode="HTML", disable_web_page_preview="true",
                       reply_markup=keyboard if (keyboard and i + 3800 >= len(text)) else None)

    def get_updates(self):
        r = self._post("getUpdates", offset=self.offset, timeout=30)
        return r.get("result", []) if r.get("ok") else []

    def is_allowed(self, uid) -> bool:
        return not self.allowed or uid in self.allowed

    # ---- дії ----
    def act_stats(self, chat):
        s = be.catalog_stats()
        fam = "\n".join(f"  • {n}: {c}" for n, c in s["top_families"][:6])
        self.send(chat, f"<b>📊 Каталог</b>\nУсього: <b>{s['total']}</b> | В наявності: <b>{s['instock']}</b> | "
                        f"Немає: {s['outofstock']}\nКатегорій: {s['categories']} | Груп: {s['families']} | "
                        f"Сер. ціна: {s['avg_price']} грн\nХарактеристик залито: {s['chars_uploaded']}\n\n"
                        f"<b>Топ груп:</b>\n{fam}", BACK)

    def act_count(self, chat):
        self.send(chat, "⏳ Питаю сайт…")
        n = be.live_product_count()
        self.send(chat, f"🌐 На сайті зараз: <b>{n}</b> товарів" if n else "Не вдалося отримати.", BACK)

    def act_recent(self, chat):
        rows = be.recent_products(12)
        body = "\n".join(f"  • <code>{r['article']}</code> {html.escape(str(r['title'])[:42])} — {r['price']} грн"
                         for r in rows)
        self.send(chat, f"<b>🆕 Останні додані:</b>\n{body}", BACK)

    def act_low(self, chat):
        rows = be.lowstock(3)[:30]
        body = "\n".join(f"  • <code>{r['article']}</code> {html.escape(str(r['title'])[:38])}: {r['qty']}" for r in rows)
        self.send(chat, f"<b>⚠️ Залишок ≤ 3 ({len(rows)}):</b>\n{body}" if rows else "Немає товарів із залишком ≤ 3.", BACK)

    def act_help(self, chat):
        self.send(chat, "<b>ℹ️ Що вміє бот</b>\n\n"
                        "📊 <b>Статистика</b> — скільки товарів, у наявності, груп, сер. ціна.\n"
                        "🌐 <b>На сайті</b> — жива к-сть товарів на сайті (запит до Horoshop).\n"
                        "🆕 <b>Останні додані</b> — нові товари.\n"
                        "⚠️ <b>Малий залишок</b> — що майже закінчилось.\n"
                        "🔎 <b>Пошук</b> / 📦 <b>Картка</b> — знайти товар за назвою/артикулом.\n"
                        "✏️ <b>Змінити ціну/залишок</b> — оновити товар на сайті.\n"
                        "🔄 <b>Синхр. ціни/залишки</b> — вивантажити свіжі ціни й наявність з УкрСкладу на сайт.\n"
                        "🧾 <b>Забрати замовлення</b> — зчитати нові замовлення з сайту і <b>списати</b> "
                        "продані товари з залишків УкрСкладу (+ видаткова накладна).", BACK)

    def prompt(self, chat, action, text):
        self.pending[chat] = action
        self.send(chat, text, kb([[("✖ Скасувати", "menu")]]))

    def confirm(self, chat, action, text):
        self.send(chat, text, kb([[("✅ Так, запустити", "go_" + action)], [("✖ Скасувати", "menu")]]))

    def run_sync(self, chat, kind):
        if chat in self.busy:
            self.send(chat, "⏳ Синхронізація вже виконується, зачекай…", BACK)
            return
        self.busy.add(chat)

        def worker():
            try:
                self.send(chat, "⏳ Запускаю… це 1–3 хв, безпечним темпом. Повідомлю, коли завершиться.")
                res = be.run_stock_sync() if kind == "stock" else be.run_order_sync()
            except Exception as exc:
                res = f"❌ Помилка: {str(exc)[:200]}"
            finally:
                self.busy.discard(chat)
            self.send(chat, res, MAIN_MENU)

        threading.Thread(target=worker, daemon=True).start()

    # ---- маршрутизація ----
    def handle_callback(self, cq):
        chat = cq["message"]["chat"]["id"]
        uid = cq.get("from", {}).get("id")
        data = cq.get("data", "")
        self._post("answerCallbackQuery", callback_query_id=cq["id"])
        if not self.is_allowed(uid):
            self.send(chat, f"⛔ Доступ лише для власника.\nТвій ID: <code>{uid}</code>")
            return
        try:
            if data == "menu":
                self.pending.pop(chat, None)
                self.send(chat, "🎣 <b>Керування магазином</b>\nОбери дію:", MAIN_MENU)
            elif data == "stats": self.act_stats(chat)
            elif data == "count": self.act_count(chat)
            elif data == "recent": self.act_recent(chat)
            elif data == "low": self.act_low(chat)
            elif data == "help": self.act_help(chat)
            elif data == "search": self.prompt(chat, "search", "🔎 Надішли слово для пошуку (напр. <i>вудка</i>):")
            elif data == "product": self.prompt(chat, "product", "📦 Надішли артикул товару (напр. <code>240</code>):")
            elif data == "setprice": self.prompt(chat, "setprice", "✏️ Надішли: <code>артикул нова_ціна</code>\nнапр. <code>VET-500 550</code>")
            elif data == "setstock": self.prompt(chat, "setstock", "✏️ Надішли: <code>артикул кількість</code>\nнапр. <code>240 10</code>")
            elif data == "syncstock":
                self.confirm(chat, "stock", "🔄 Вивантажити свіжі <b>ціни й наявність</b> з УкрСкладу на сайт?\n(безпечно, ~1 файл, кілька запитів)")
            elif data == "syncorders":
                self.confirm(chat, "orders", "🧾 Зчитати нові замовлення з сайту і <b>списати</b> продані товари з залишків УкрСкладу?")
            elif data == "go_stock": self.run_sync(chat, "stock")
            elif data == "go_orders": self.run_sync(chat, "orders")
            else:
                self.send(chat, "Невідома дія.", BACK)
        except Exception:
            self.send(chat, f"⚠️ Помилка:\n<pre>{html.escape(traceback.format_exc()[-500:])}</pre>", BACK)

    def handle_message(self, msg):
        chat = msg["chat"]["id"]
        uid = msg.get("from", {}).get("id")
        text = (msg.get("text") or "").strip()
        if not text:
            return
        if text.lower().lstrip("/").split("@")[0] == "whoami":
            self.send(chat, f"Твій Telegram ID: <code>{uid}</code>")
            return
        if not self.is_allowed(uid):
            self.send(chat, f"⛔ Доступ лише для власника.\nТвій ID: <code>{uid}</code>\n"
                            f"Додай його в config.json → allowed_user_ids.")
            return
        # очікуваний ввід?
        action = self.pending.pop(chat, None)
        if action:
            self.process_input(chat, action, text)
            return
        # будь-який текст / команда → головне меню
        self.send(chat, "🎣 <b>Керування магазином vsedliarybalky.com.ua</b>\nОбери дію:", MAIN_MENU)

    def process_input(self, chat, action, text):
        try:
            if action == "search":
                rows = be.search_products(text)
                body = "\n".join(f"  • <code>{str(p['article']).strip()}</code> "
                                 f"{html.escape(str(p.get('title'))[:42])} — {p.get('price')} грн" for p in rows)
                self.send(chat, f"<b>🔎 Знайдено {len(rows)}:</b>\n{body}" if rows else "Нічого не знайдено.", BACK)
            elif action == "product":
                d = be.product_detail(text)
                if not d:
                    self.send(chat, "Товар не знайдено.", BACK); return
                chars = "\n".join(f"    – {html.escape(str(x.get('name')))}: {html.escape(str(x.get('value')))}"
                                  for x in d["params"][:15])
                self.send(chat, f"<b>{html.escape(str(d['title']))}</b>\nАртикул: <code>{d['article']}</code> | "
                                f"id: {d['id']}\nЦіна: {d['price']} {d['currency']} | Залишок: {d['qty']}\n"
                                f"Група: {d['family']} | Бренд: {d['brand']} | Фото: {d['images']}\n"
                                f"<b>Характеристики ({len(d['params'])}):</b>\n{chars}", BACK)
            elif action in ("setprice", "setstock"):
                parts = text.split()
                if len(parts) < 2:
                    self.send(chat, "Формат: <code>артикул значення</code>", BACK); return
                field = "price" if action == "setprice" else "quantity"
                ok, m = be.set_field(parts[0], field, parts[1])
                self.send(chat, ("✅ " if ok else "❌ ") + m, MAIN_MENU)
        except Exception:
            self.send(chat, f"⚠️ Помилка:\n<pre>{html.escape(traceback.format_exc()[-500:])}</pre>", BACK)

    # ---- головний цикл ----
    def run(self):
        me = self._post("getMe")
        if not me.get("ok"):
            raise SystemExit(f"Токен недійсний: {me}")
        print(f"Бот @{me['result']['username']} запущено. Дозволені: {self.allowed or 'УСІ (налаштуй!)'}", flush=True)
        while True:
            try:
                for upd in self.get_updates():
                    self.offset = upd["update_id"] + 1
                    OFFSET_FILE.write_text(str(self.offset))
                    if "callback_query" in upd:
                        self.handle_callback(upd["callback_query"])
                    elif "message" in upd:
                        self.handle_message(upd["message"])
            except KeyboardInterrupt:
                print("Зупинено.", flush=True); break
            except Exception as exc:
                print("loop err:", exc, flush=True); time.sleep(3)


if __name__ == "__main__":
    Bot(load_config()).run()
