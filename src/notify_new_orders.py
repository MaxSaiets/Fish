# -*- coding: utf-8 -*-
r"""
notify_new_orders.py — сповіщення в Telegram про НОВІ замовлення з сайту.

Тягне замовлення з Horoshop тим самим робочим механізмом, що й sync_orders.py
(Playwright → /adminLegacy/handlers/orders.php), порівнює з журналом уже
надісланих і шле у Telegram лише НОВІ. Працює локально, без VPS; токен і
отримувачі беруться з src/telegram_bot/config.json (той самий бот, що керує
магазином).

Запуск:
  cd D:\FISH\fish-sync
  python src\notify_new_orders.py            # надіслати сповіщення про нові
  python src\notify_new_orders.py --seed     # позначити поточні як надіслані БЕЗ сповіщень (перший раз)
  python src\notify_new_orders.py --test      # надіслати тестове повідомлення й вийти
  python src\notify_new_orders.py --days 3    # дивитись замовлення за N днів (деф. 3)

Планувальник: запускати кожні 5-10 хв (див. docs/setup_scheduled_tasks.ps1).
Журнал надісланих: data/notified_orders.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

NOTIFIED_FILE = ROOT / "data" / "notified_orders.json"
ALERTS_STATE = ROOT / "data" / "notify_alerts_state.json"
TG_CONFIG = ROOT / "src" / "telegram_bot" / "config.json"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    ef = ROOT / ".env"
    if ef.exists():
        for line in ef.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def load_tg() -> tuple[str, list[int]]:
    """Токен і отримувачі.

    ПРІОРИТЕТ — .env (TELEGRAM_BOT_TOKEN / TELEGRAM_ADMIN_IDS), бо саме звідти
    бере токен сам бот. Раніше цей скрипт читав ЛИШЕ config.json, і коли там
    лишився токен старого (відкликаного) бота, сповіщення про замовлення
    мовчки не доходили: Telegram відповідав 'Unauthorized', а скрипт завершувався
    успішно. Знайдено 31.07.2026 на живому тестовому замовленні.
    config.json лишається запасним варіантом.
    """
    env = load_env()
    token = (env.get("TELEGRAM_BOT_TOKEN") or "").strip()
    ids = [int(x) for x in (env.get("TELEGRAM_ADMIN_IDS") or "").split(",") if x.strip().isdigit()]

    if not token or not ids:
        try:
            cfg = json.loads(TG_CONFIG.read_text(encoding="utf-8"))
            token = token or (cfg.get("token") or "").strip()
            ids = ids or list(cfg.get("allowed_user_ids") or [])
        except Exception:
            pass
    return token, ids


def tg_send(token: str, chat_id: int, text: str) -> bool:
    api = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(api, data={"chat_id": chat_id, "text": text,
                                     "parse_mode": "HTML", "disable_web_page_preview": "true"},
                          timeout=30)
        j = r.json()
        if not j.get("ok"):
            print(f"  [TG] помилка для {chat_id}: {j.get('description')}")
        return bool(j.get("ok"))
    except Exception as exc:  # noqa: BLE001
        print(f"  [TG] виняток для {chat_id}: {exc}")
        return False


def load_notified() -> set[str]:
    if NOTIFIED_FILE.exists():
        try:
            return set(json.loads(NOTIFIED_FILE.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            return set()
    return set()


def save_notified(ids: set[str]) -> None:
    NOTIFIED_FILE.parent.mkdir(parents=True, exist_ok=True)
    NOTIFIED_FILE.write_text(json.dumps(sorted(ids), ensure_ascii=False, indent=1),
                             encoding="utf-8")


def format_order(o: dict, base: str, header: str = "НОВЕ ЗАМОВЛЕННЯ") -> str:
    import html as H
    lines = [f"🎣 <b>{header} #{H.escape(str(o.get('horoshop_id','?')))}</b>"]
    if o.get("date"):
        lines.append(f"📅 {H.escape(str(o['date']))}")
    if o.get("customer"):
        lines.append(f"👤 {H.escape(str(o['customer']))}")
    if o.get("phone"):
        lines.append(f"📞 {H.escape(str(o['phone']))}")
    if o.get("total"):
        lines.append(f"💰 <b>{H.escape(str(o['total']))} грн</b>")
    items = o.get("items") or []
    if items:
        lines.append("🛒 Товари:")
        for it in items[:20]:
            name = it.get("name") or it.get("title") or it.get("article") or "?"
            qty = it.get("qty") or it.get("quantity") or it.get("kolvo") or ""
            lines.append(f"  • {H.escape(str(name))[:60]}" + (f" ×{H.escape(str(qty))}" if qty else ""))
        if len(items) > 20:
            lines.append(f"  … і ще {len(items) - 20}")
    oid = o.get("horoshop_id")
    if oid:
        lines.append(f'🔗 <a href="{base}/adminLegacy/handlers/orders.php?view&id={oid}">Відкрити в адмінці</a>')
    return "\n".join(lines)


# ────────── автоалерти (топ-товар у нулі, застарілий синк) + тижневий звіт ──────────

def _load_alerts_state() -> dict:
    if ALERTS_STATE.exists():
        try:
            return json.loads(ALERTS_STATE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _save_alerts_state(state: dict) -> None:
    ALERTS_STATE.parent.mkdir(parents=True, exist_ok=True)
    ALERTS_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def run_extra_alerts(token: str, recipients: list[int]) -> None:
    """Разом із перевіркою замовлень (кожні 10 хв) шлемо:
      1) алерт, коли ТОП-товар за виручкою впав у нуль (одноразово на товар);
      2) алерт, якщо дані з УкрСкладу не оновлювались > 24 год (раз на добу);
      3) тижневий звіт щопонеділка (раз на тиждень).
    Стан — data/notify_alerts_state.json. Помилки тут не валять основний потік.
    """
    try:
        import bot_dashboard
    except Exception as exc:  # noqa: BLE001
        print(f"  [alerts] bot_dashboard недоступний: {exc}")
        return
    state = _load_alerts_state()
    today = datetime.now().strftime("%Y-%m-%d")

    # 1) топ-товари, що впали в нуль
    try:
        stale = bot_dashboard.stale_top_sellers(limit=20)
        known = set(state.get("stale_kods") or [])
        fresh = [r for r in stale if r["kod"] not in known]
        if fresh:
            lines = ["🔻 <b>ХОДОВИЙ ТОВАР ЗАКІНЧИВСЯ</b>",
                     "<i>Добре продавався — тепер залишок 0. Варто замовити.</i>", ""]
            for r in fresh[:15]:
                lines.append(f"• <b>{r['name']}</b> · арт. {r['kod']}")
            text = "\n".join(lines)
            for uid in recipients:
                tg_send(token, uid, text)
            print(f"  [alerts] нових нулів по топу: {len(fresh)}")
        state["stale_kods"] = [r["kod"] for r in stale]
    except Exception as exc:  # noqa: BLE001
        print(f"  [alerts] stale-top: {exc}")

    # 2) синк не проходив > 24 год
    try:
        products = ROOT / "data" / "products.json"
        if products.exists():
            age_h = (datetime.now().timestamp() - products.stat().st_mtime) / 3600
            if age_h > 24 and state.get("last_sync_alert") != today:
                for uid in recipients:
                    tg_send(token, uid,
                            f"⚠️ <b>Синхронізація не працює</b>\n"
                            f"Дані з УкрСкладу не оновлювались {age_h:.0f} год.\n"
                            f"Перевір, чи ввімкнений ноутбук магазину і чи працюють задачі Планувальника.")
                state["last_sync_alert"] = today
                print(f"  [alerts] синк застарів: {age_h:.0f} год")
    except Exception as exc:  # noqa: BLE001
        print(f"  [alerts] sync-age: {exc}")

    # 3) тижневий звіт щопонеділка
    try:
        week = datetime.now().strftime("%G-W%V")
        if datetime.now().weekday() == 0 and state.get("last_weekly") != week:
            report = "🗓 <b>ТИЖНЕВИЙ ЗВІТ</b>\n\n" + bot_dashboard.dashboard_html()
            for uid in recipients:
                tg_send(token, uid, report)
            state["last_weekly"] = week
            print("  [alerts] тижневий звіт надіслано")
    except Exception as exc:  # noqa: BLE001
        print(f"  [alerts] weekly: {exc}")

    _save_alerts_state(state)


def main() -> int:
    ap = argparse.ArgumentParser(description="Сповіщення про нові замовлення в Telegram")
    ap.add_argument("--days", type=int, default=3, help="За скільки днів дивитись замовлення")
    ap.add_argument("--seed", action="store_true",
                    help="Позначити поточні замовлення як надіслані БЕЗ сповіщень")
    ap.add_argument("--test", action="store_true", help="Надіслати тестове повідомлення й вийти")
    ap.add_argument("--list", action="store_true", dest="list_only",
                    help="Лише показати замовлення (для бота): без сповіщень і без запису в журнал")
    ap.add_argument("--headful", action="store_true")
    args = ap.parse_args()

    token, recipients = load_tg()
    if not recipients:
        print("У config.json порожній allowed_user_ids — нема кому слати. "
              "Впишіть свій Telegram ID (дізнатись: напишіть боту /whoami).")
        return 1

    if args.test:
        msg = ("✅ <b>Тест сповіщень про замовлення</b>\n"
               "Якщо ви це бачите — Telegram-сповіщення налаштовані правильно. "
               "Реальні замовлення з сайту приходитимуть сюди автоматично.")
        ok = sum(tg_send(token, uid, msg) for uid in recipients)
        print(f"Тест надіслано: {ok}/{len(recipients)}")
        return 0 if ok else 1

    env = load_env()
    from horoshop_sync import get_base_url
    base = get_base_url(env)
    from sync_orders import fetch_orders_playwright

    since = datetime.now() - timedelta(days=args.days)
    print(f"Читаю замовлення за {args.days} дн...")
    orders = fetch_orders_playwright(base, env.get("HOROSHOP_LOGIN", ""),
                                     env.get("HOROSHOP_PASS", ""), since_date=since,
                                     headful=args.headful)
    print(f"Знайдено замовлень: {len(orders)}")

    if args.list_only:
        # Режим для кнопки «🛒 Замовлення» в боті: показати, нічого не міняти.
        if not orders:
            print(f"📭 Замовлень за {args.days} дн немає.")
            return 0
        for o in orders:
            print("===ORDER===")
            print(format_order(o, base, header="ЗАМОВЛЕННЯ"))
        return 0

    notified = load_notified()
    fresh = [o for o in orders if str(o.get("horoshop_id")) not in notified]

    if args.seed:
        for o in orders:
            notified.add(str(o.get("horoshop_id")))
        save_notified(notified)
        print(f"Seed: позначено {len(orders)} замовлень як надіслані (без сповіщень).")
        return 0

    if not fresh:
        print("Нових замовлень немає.")
        run_extra_alerts(token, recipients)
        return 0

    sent = 0
    for o in fresh:
        text = format_order(o, base)
        ok_any = False
        for uid in recipients:
            if tg_send(token, uid, text):
                ok_any = True
        if ok_any:
            notified.add(str(o.get("horoshop_id")))
            sent += 1
            print(f"  ✅ сповіщено про #{o.get('horoshop_id')}")
    save_notified(notified)
    print(f"Надіслано сповіщень про {sent} нових замовлень.")
    run_extra_alerts(token, recipients)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
