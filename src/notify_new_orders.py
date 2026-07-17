# -*- coding: utf-8 -*-
"""
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

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

NOTIFIED_FILE = ROOT / "data" / "notified_orders.json"
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
    cfg = json.loads(TG_CONFIG.read_text(encoding="utf-8"))
    return cfg["token"], list(cfg.get("allowed_user_ids") or [])


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


def format_order(o: dict, base: str) -> str:
    import html as H
    lines = [f"🎣 <b>НОВЕ ЗАМОВЛЕННЯ #{H.escape(str(o.get('horoshop_id','?')))}</b>"]
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Сповіщення про нові замовлення в Telegram")
    ap.add_argument("--days", type=int, default=3, help="За скільки днів дивитись замовлення")
    ap.add_argument("--seed", action="store_true",
                    help="Позначити поточні замовлення як надіслані БЕЗ сповіщень")
    ap.add_argument("--test", action="store_true", help="Надіслати тестове повідомлення й вийти")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
