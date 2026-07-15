"""
Завантажує нові замовлення з Horoshop і зберігає у CSV для введення в УкрСклад.

Horoshop не надає повноцінний orders API на базовому плані, тому
скрипт використовує CSV-експорт через legacy admin.

Запуск:
  cd D:\FISH\fish-sync
  python src\fetch_horoshop_orders.py
  python src\fetch_horoshop_orders.py --days 3      # замовлення за останні 3 дні

Результат зберігається у:
  data\horoshop_orders_YYYYMMDD.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings()

ROOT = Path(r"D:\FISH\fish-sync")
ENV_FILE = ROOT / ".env"
DATA_DIR = ROOT / "data"
sys.path.insert(0, str(ROOT / "src"))


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def fetch_orders_legacy(session: requests.Session, base: str, days: int = 7) -> list[dict]:
    """Отримує замовлення через legacy admin data endpoint."""
    date_from = (datetime.now() - timedelta(days=days)).strftime("%d.%m.%Y")

    # Спочатку отримуємо список замовлень через iframe legacy admin
    resp = session.get(
        f"{base}/adminLegacy/data.php",
        params={"handler": "3", "dateFrom": date_from},
        verify=False,
        timeout=30,
    )

    if resp.status_code != 200:
        print(f"[WARN] legacy orders page: {resp.status_code}")
        return []

    # Парсимо HTML таблицю замовлень
    from html.parser import HTMLParser

    class TableParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.rows: list[list[str]] = []
            self._current: list[str] = []
            self._in_td = False
            self._in_header = False
            self.headers: list[str] = []

        def handle_starttag(self, tag: str, attrs: list) -> None:
            if tag == "tr":
                self._current = []
            elif tag in ("td", "th"):
                self._in_td = True
                self._in_header = tag == "th"

        def handle_endtag(self, tag: str) -> None:
            if tag in ("td", "th"):
                self._in_td = False
                self._in_header = False
            elif tag == "tr" and self._current:
                if self._in_header or (self.rows and not self.headers):
                    self.headers = self._current
                else:
                    self.rows.append(self._current)
                self._current = []

        def handle_data(self, data: str) -> None:
            if self._in_td:
                text = data.strip()
                if self._current and not text:
                    return
                if self._in_td:
                    self._current.append(text)

    parser = TableParser()
    parser.feed(resp.text)

    if not parser.rows:
        return []

    headers = parser.headers or [f"col_{i}" for i in range(20)]
    orders = []
    for row in parser.rows:
        if len(row) < 3:
            continue
        order = {headers[i] if i < len(headers) else f"col_{i}": v for i, v in enumerate(row)}
        orders.append(order)

    return orders


def fetch_orders_api(session: requests.Session, base: str, token: str, days: int = 7) -> list[dict]:
    """Спроба через Horoshop API (може повернути UNDEFINED_FUNCTION)."""
    date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    resp = session.post(
        f"{base}/api/orders/",
        json={"token": token, "filter": {"date_from": date_from}},
        verify=False,
        timeout=30,
    )
    data = resp.json()
    if data.get("status") == "OK":
        return (data.get("response") or {}).get("orders") or []
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description="Завантажує замовлення з Horoshop")
    ap.add_argument("--days", type=int, default=7, help="За скільки днів завантажити замовлення")
    args = ap.parse_args()

    env = load_env()
    base = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")

    from horoshop_sync import auth, get_base_url
    base = get_base_url(env)

    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync/1.0"

    token = auth(session, base, env.get("HOROSHOP_LOGIN", ""), env.get("HOROSHOP_PASS", ""))
    print(f"Авторизація OK. Завантаження замовлень за {args.days} дн...")

    # Спочатку API
    orders = fetch_orders_api(session, base, token, args.days)
    source = "API"

    # Якщо API не дає — legacy
    if not orders:
        print("API не надає замовлень, спроба legacy admin...")
        orders = fetch_orders_legacy(session, base, args.days)
        source = "legacy"

    if not orders:
        print("Замовлень не знайдено або API недоступний.")
        print()
        print("=== РУЧНИЙ СПОСІБ ===")
        print(f"Відкрийте: {base}/edit/orders/all")
        print("Натисніть кнопку 'Експорт' → завантажте CSV")
        print("Збережіть файл у: data\\horoshop_orders_manual.csv")
        return 0

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / f"horoshop_orders_{datetime.now().strftime('%Y%m%d')}.csv"

    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        if orders:
            writer = csv.DictWriter(f, fieldnames=list(orders[0].keys()))
            writer.writeheader()
            writer.writerows(orders)

    print(f"Збережено {len(orders)} замовлень ({source}) → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
