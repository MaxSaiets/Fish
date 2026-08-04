# -*- coding: utf-8 -*-
"""
diagnose.py — ПОВНІСТЮ READ-ONLY перевірка всього ланцюга синхронізації.

Відповідає на три питання, які неможливо перевірити «на око»:
  1. Чи оновлюється наявність товарів на сайті з УкрСкладу?
  2. Чи приходять сповіщення про замовлення в Telegram?
  3. Чи списуються продані товари з УкрСкладу?

Нічого не змінює: не пише в УкрСклад, не вантажить на сайт, не шле повідомлень.
Читає лише файли, локальну копію бази та робить GET-запити до адмінки.

Запуск:
  python src\\diagnose.py            # текстовий звіт
  python src\\diagnose.py --json     # машинний формат

У боті: «⚙️ Ще» → «🧪 Діагностика».

ВАЖЛИВО: запускати на тій машині, яку перевіряємо. Ноут магазину і ноут
розробки мають РІЗНІ бази УкрСкладу і різні журнали — звіт стосується лише
тієї машини, де запущений.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

TASKS = {
    "UkrSkladToHoroshop_StockSync": "залишки/ціни УкрСклад → сайт",
    "HoroshopOrders_ToUkrSklad": "замовлення → списання в УкрСкладі",
    "HoroshopOrders_TelegramNotify": "сповіщення про замовлення",
    "FishSyncBot": "сам Telegram-бот",
}

# Задачі зі СТАРОГО setup_task_scheduler.ps1. Якщо вони існують ОДНОЧАСНО з
# новими — синхронізація йде двічі, а замовлення можуть списатися ДВІЧІ.
LEGACY_TASKS = {
    "FishSyncStock": "дублює залишки",
    "FishSyncOrders": "дублює замовлення — РИЗИК подвійного списання",
    "FishSyncFullPipeline": "дублює повний цикл",
    "FishSyncServer": "локальний сервер фідів (не потрібен)",
}


def _age(ts: float) -> str:
    d = time.time() - ts
    if d < 3600:
        return f"{int(d // 60)} хв тому"
    if d < 86400:
        return f"{int(d // 3600)} год тому"
    return f"{int(d // 86400)} дн тому"


def _env() -> dict:
    env = {}
    ef = ROOT / ".env"
    if ef.exists():
        for line in ef.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


# ─────────────────────────── 1. Заплановані задачі ───────────────────────────

def check_tasks() -> list[dict]:
    """Стан задач Планувальника Windows: увімкнена, коли востаннє, з яким кодом."""
    out = []
    all_names = list(TASKS) + list(LEGACY_TASKS)
    ps = (
        "Get-ScheduledTask | Where-Object { $_.TaskName -in @(" +
        ",".join(f"'{t}'" for t in all_names) +
        ") } | ForEach-Object { $i = $_ | Get-ScheduledTaskInfo; "
        "[pscustomobject]@{Name=$_.TaskName; State=$_.State.ToString(); "
        "Last=$i.LastRunTime; Result=$i.LastTaskResult; Next=$i.NextRunTime} } | ConvertTo-Json"
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=60)
        data = json.loads(r.stdout or "[]")
        if isinstance(data, dict):
            data = [data]
    except Exception as exc:  # noqa: BLE001
        return [{"name": "—", "error": str(exc)}]

    found = {d.get("Name"): d for d in data}
    for name, descr in TASKS.items():
        d = found.get(name)
        if not d:
            out.append({"name": name, "descr": descr, "state": "НЕ СТВОРЕНА", "ok": False})
            continue
        state = d.get("State", "?")
        result = d.get("Result")
        last = str(d.get("Last") or "")
        m = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})", last) or re.search(r"(\d+)", last)
        last_h = None
        if m and m.group(1).isdigit():           # /Date(1234567890)/
            last_h = (time.time() - int(m.group(1)) / 1000) / 3600
        elif m:
            try:
                last_h = (time.time() - datetime.fromisoformat(m.group(1)).timestamp()) / 3600
            except Exception:  # noqa: BLE001
                last_h = None
        out.append({
            "name": name, "descr": descr, "state": state,
            "result": result, "last_hours": last_h,
            "ok": state == "Ready" and result == 0,
        })

    # старі задачі-дублікати — якщо вони увімкнені, це прямий ризик
    for name, descr in LEGACY_TASKS.items():
        d = found.get(name)
        if d and d.get("State") != "Disabled":
            out.append({"name": name, "descr": descr, "state": d.get("State"),
                        "legacy": True, "ok": False})
    return out


# ─────────────────────────── 2. УкрСклад ───────────────────────────

def check_ukrsklad() -> dict:
    """База знайдена? свіжа? скільки товарів? чи є накладні з сайту?"""
    res: dict = {"ok": False}
    try:
        import ukrsklad as u
    except Exception as exc:  # noqa: BLE001
        res["error"] = f"модуль недоступний: {exc}"
        return res

    db = u.LIVE_DB
    res["db_path"] = str(db)
    if not db or not db.exists():
        res["error"] = "база УкрСкладу не знайдена"
        return res
    res["db_mb"] = round(db.stat().st_size / 1024 / 1024)
    res["db_age"] = _age(db.stat().st_mtime)
    res["db_age_hours"] = (time.time() - db.stat().st_mtime) / 3600

    # читаємо ЧЕРЕЗ СНАПШОТ — жива база не блокується і не змінюється
    try:
        snap = u.take_snapshot()
        os.environ["PATH"] = str(u.FBCLIENT.parent) + os.pathsep + os.environ.get("PATH", "")
        import fdb
        conn = fdb.connect(database=str(snap), user=u.USER, password=u.PASSWORD,
                           charset=u.CHARSET, fb_library_name=str(u.FBCLIENT))
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM TOVAR_NAME WHERE VISIBLE = 1 AND IS_USLUGA = 0")
            res["products"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM TOVAR_ZAL WHERE VISIBLE = 1 AND KOLVO > 0")
            res["in_stock"] = cur.fetchone()[0]
            # накладні, створені нашою синхронізацією замовлень
            cur.execute("SELECT COUNT(*), MAX(DATE_DOK) FROM VNAKL WHERE DOC_DESCR LIKE 'Horoshop%'")
            row = cur.fetchone()
            res["horoshop_invoices"] = row[0] or 0
            res["last_horoshop_invoice"] = str(row[1]) if row[1] else None
        finally:
            conn.close()
        res["ok"] = True
    except Exception as exc:  # noqa: BLE001
        res["error"] = f"читання бази: {exc}"
    return res


# ─────────────────────────── 3. Журнали й логи ───────────────────────────

def check_logs() -> dict:
    logs = ROOT / "logs"
    res: dict = {}

    def last_log(pattern: str) -> dict | None:
        files = sorted(logs.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True) \
            if logs.is_dir() else []
        if not files:
            return None
        f = files[0]
        info = {"file": f.name, "age": _age(f.stat().st_mtime),
                "age_hours": (time.time() - f.stat().st_mtime) / 3600}
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
            info["status"] = payload.get("status")
            steps = payload.get("steps") or {}
            sync = steps.get("playwright_sync") or {}
            if sync:
                info["updated"] = sync.get("updated")
                info["dry_run"] = sync.get("dry_run")
            if "summary" in payload:
                info["summary"] = payload["summary"]
            if payload.get("orders"):
                info["order_results"] = [o.get("ukrsklad_result", {}).get("status")
                                         for o in payload["orders"]]
        except Exception:  # noqa: BLE001
            pass
        return info

    res["stock_sync"] = last_log("stock_pw_*.log")
    res["orders"] = last_log("orders_*.log")
    res["pipeline"] = last_log("pipeline_*.log")

    for name, path in (("products", ROOT / "data" / "products.json"),
                       ("notified_orders", ROOT / "data" / "notified_orders.json"),
                       ("processed_orders", ROOT / "data" / "processed_orders.json")):
        if path.exists():
            entry = {"age": _age(path.stat().st_mtime)}
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    entry["count"] = len(data)
                elif isinstance(data, dict) and "products" in data:
                    entry["count"] = len(data["products"])
            except Exception:  # noqa: BLE001
                pass
            res[name] = entry
        else:
            res[name] = {"age": "немає файлу"}
    return res


# ─────────────────────────── 4. Telegram ───────────────────────────

def check_telegram() -> dict:
    import requests
    env = _env()
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    ids = [x for x in (env.get("TELEGRAM_ADMIN_IDS") or "").split(",") if x.strip()]
    res = {"admins": len(ids), "ok": False}
    if not token:
        res["error"] = "TELEGRAM_BOT_TOKEN не заданий у .env"
        return res
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=20).json()
        if r.get("ok"):
            res["ok"] = True
            res["username"] = r["result"].get("username")
        else:
            res["error"] = r.get("description", "токен відхилено")
    except Exception as exc:  # noqa: BLE001
        res["error"] = str(exc)
    return res


# ───────────── 5. Сайт: чи збігається наявність із УкрСкладом ─────────────

def check_site_sync(sample: int = 12) -> dict:
    """Порівнює наявність на сайті з УкрСкладом на вибірці товарів.

    Це ПРЯМИЙ доказ того, чи доїжджають залишки: якщо синхронізація працює,
    розбіжностей майже немає. Багато розбіжностей = залишки не оновлюються.
    """
    res: dict = {"checked": 0, "match": 0, "mismatch": [],
                 "price_checked": 0, "price_match": 0, "price_mismatch": [], "ok": False}
    try:
        import urllib3
        urllib3.disable_warnings()
        import requests
        from apply_horoshop_menu_fixes import LegacyFormParser, auth, get_base_url, load_env

        env = load_env()
        base = get_base_url(env)
        id_map_file = ROOT / "data" / "article_id_full.json"
        products_file = ROOT / "data" / "products.json"
        if not id_map_file.exists() or not products_file.exists():
            res["error"] = "немає data/article_id_full.json або products.json"
            return res
        id_map = json.loads(id_map_file.read_text(encoding="utf-8"))
        raw = json.loads(products_file.read_text(encoding="utf-8"))
        plist = raw.get("products", raw) if isinstance(raw, dict) else raw
        by_kod = {str(p.get("kod") or "").strip(): p for p in plist}

        # вибірка: половина з наявних, половина з нульових — щоб ловити обидва напрямки
        with_stock = [k for k, p in by_kod.items() if k in id_map and float(p.get("stock") or 0) > 0]
        no_stock = [k for k, p in by_kod.items() if k in id_map and float(p.get("stock") or 0) <= 0]
        step_a = max(1, len(with_stock) // max(1, sample // 2))
        step_b = max(1, len(no_stock) // max(1, sample // 2))
        picked = with_stock[::step_a][: sample // 2] + no_stock[::step_b][: sample // 2]

        s = requests.Session()
        s.headers["User-Agent"] = "fish-diagnose/1.0"
        auth(s, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

        for art in picked:
            pid = id_map.get(art)
            url = (f"{base}/adminLegacy/edit.php?id={pid}&parent=97"
                   f"&action=edit&handler=381&checkcode=yamete_kudasai")
            try:
                r = s.get(url, timeout=45, verify=False)
                if r.status_code != 200 or "modifications[0]" not in r.text:
                    continue
                p = LegacyFormParser()
                p.feed(r.text)
                f = dict(p.fields)
                site_available = str(f.get("modifications[0][presence]", "")) == "1"
                ukr_available = float(by_kod[art].get("stock") or 0) > 0
                res["checked"] += 1
                if site_available == ukr_available:
                    res["match"] += 1
                else:
                    res["mismatch"].append({
                        "article": art,
                        "site": "є" if site_available else "немає",
                        "ukrsklad": "є" if ukr_available else "немає",
                    })

                # ціна змінюється частіше за наявність — чутливіший індикатор
                try:
                    site_price = float(f.get("modifications[0][price]") or 0)
                    ukr_price = float(by_kod[art].get("cena_r") or 0)
                    if site_price > 0 and ukr_price > 0:
                        res["price_checked"] += 1
                        if abs(site_price - ukr_price) < 0.01:
                            res["price_match"] += 1
                        else:
                            res["price_mismatch"].append(
                                {"article": art, "site": site_price, "ukrsklad": ukr_price})
                except (TypeError, ValueError):
                    pass
            except Exception:  # noqa: BLE001
                continue
        res["ok"] = res["checked"] > 0
    except Exception as exc:  # noqa: BLE001
        res["error"] = str(exc)
    return res


# ─────────────────────────── Звіт ───────────────────────────

def full_report() -> dict:
    return {
        "machine": os.environ.get("COMPUTERNAME", "?"),
        "when": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "tasks": check_tasks(),
        "ukrsklad": check_ukrsklad(),
        "logs": check_logs(),
        "telegram": check_telegram(),
        "site_sync": check_site_sync(),
    }


def full_report_html() -> str:
    r = full_report()
    L = [f"🧪 <b>ДІАГНОСТИКА</b> · {r['machine']} · {r['when']}", ""]

    # --- 1. Автоматичні задачі
    L.append("⏰ <b>Автоматичні задачі</b>")
    for t in r["tasks"]:
        if t.get("legacy"):
            L.append(f"   🔴 СТАРА ЗАДАЧА <code>{t['name']}</code> увімкнена — {t['descr']}")
        elif t.get("state") == "НЕ СТВОРЕНА":
            L.append(f"   ❌ {t['descr']} — задача не створена")
        elif t.get("state") == "Disabled":
            L.append(f"   ⛔ {t['descr']} — ВИМКНЕНА")
        else:
            last = f"{t['last_hours']:.0f} год тому" if t.get("last_hours") is not None else "невідомо"
            mark = "✅" if t.get("result") == 0 else "⚠️"
            L.append(f"   {mark} {t['descr']} — {last}"
                     + (f", код {t['result']}" if t.get("result") not in (0, None) else ""))

    # --- 2. УкрСклад + списання
    u = r["ukrsklad"]
    L += ["", "🗄 <b>УкрСклад</b>"]
    if not u.get("ok"):
        L.append(f"   ❌ {u.get('error', 'недоступний')}")
    else:
        mark = "✅" if u["db_age_hours"] < 48 else "⚠️"
        L.append(f"   {mark} База: {u['db_mb']} МБ, змінена {u['db_age']}")
        L.append(f"   📦 Товарів: {u['products']} · у наявності: {u['in_stock']}")
        inv = u.get("horoshop_invoices", 0)
        if inv:
            L.append(f"   ✅ Списань із сайту: <b>{inv}</b> (остання {u.get('last_horoshop_invoice')})")
        else:
            L.append("   ⚠️ Списань із сайту ЩЕ НЕ БУЛО (жодної накладної «Horoshop #»)")

    # --- 3. Останні прогони
    lg = r["logs"]
    L += ["", "🔄 <b>Останні прогони</b>"]
    st = lg.get("stock_sync")
    if st:
        extra = " (dry-run!)" if st.get("dry_run") else ""
        upd = f", оновлено {st['updated']}" if st.get("updated", -1) and st.get("updated", -1) > 0 else ""
        mark = "✅" if st.get("status") == "ok" and st["age_hours"] < 24 else "⚠️"
        L.append(f"   {mark} Залишки: {st['age']}, {st.get('status')}{upd}{extra}")
    else:
        L.append("   ⚠️ Залишки: прогонів не було")
    od = lg.get("orders")
    if od:
        dry = " (dry-run!)" if "dry_run" in (od.get("order_results") or []) else ""
        L.append(f"   {'✅' if od.get('status') == 'ok' else '⚠️'} Замовлення: {od['age']}, "
                 f"{od.get('status')}{dry}")
    else:
        L.append("   ⚠️ Замовлення: прогонів не було")
    L.append(f"   📄 Дані з УкрСкладу: {lg.get('products', {}).get('age')}")
    L.append(f"   🔔 Сповіщено про замовлень: {lg.get('notified_orders', {}).get('count', 0)}")
    L.append(f"   🧾 Списано замовлень: {lg.get('processed_orders', {}).get('count', 0)}")

    # --- 4. Telegram
    tg = r["telegram"]
    L += ["", "💬 <b>Telegram</b>"]
    if tg.get("ok"):
        L.append(f"   ✅ Бот @{tg.get('username')} · отримувачів сповіщень: {tg['admins']}")
        if tg["admins"] < 2:
            L.append("   ⚠️ Отримувач лише один — власниця магазину сповіщень НЕ бачить")
    else:
        L.append(f"   ❌ {tg.get('error')}")

    # --- 5. Сайт vs УкрСклад
    ss = r["site_sync"]
    L += ["", "🌐 <b>Наявність на сайті vs УкрСклад</b>"]
    if not ss.get("ok"):
        L.append(f"   ⚠️ {ss.get('error', 'перевірити не вдалося')}")
    else:
        bad = len(ss["mismatch"])
        mark = "✅" if bad == 0 else ("⚠️" if bad <= ss["checked"] // 3 else "❌")
        L.append(f"   {mark} Наявність збігається: {ss['match']} з {ss['checked']}")
        for m in ss["mismatch"][:5]:
            L.append(f"      • {m['article']}: сайт «{m['site']}», УкрСклад «{m['ukrsklad']}»")
        pbad = len(ss.get("price_mismatch") or [])
        if ss.get("price_checked"):
            pmark = "✅" if pbad == 0 else ("⚠️" if pbad <= ss["price_checked"] // 3 else "❌")
            L.append(f"   {pmark} Ціни збігаються: {ss['price_match']} з {ss['price_checked']}")
            for m in ss["price_mismatch"][:5]:
                L.append(f"      • {m['article']}: сайт {m['site']:g} грн, УкрСклад {m['ukrsklad']:g} грн")
        if bad or pbad:
            L.append("   <i>Розбіжності = дані з УкрСкладу на сайт не доїжджають "
                     "(або ця машина має стару копію бази).</i>")

    return "\n".join(L)


def main() -> int:
    if "--json" in sys.argv:
        print(json.dumps(full_report(), ensure_ascii=False, indent=2, default=str))
        return 0
    txt = full_report_html()
    for tag in ("<b>", "</b>", "<i>", "</i>", "<code>", "</code>"):
        txt = txt.replace(tag, "")
    print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
