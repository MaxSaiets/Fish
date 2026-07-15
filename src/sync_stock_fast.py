"""
Швидка синхронізація залишків та цін УкрСклад → Horoshop.

Запускається кожну годину через Windows Task Scheduler.
Робить тільки: snapshot → extract → Horoshop price/stock push.
НЕ робить: AI-описи, фото, XML-рендер, аудити — лише залишки + ціни.

Запуск вручну:
  cd D:\FISH\fish-sync
  python src\sync_stock_fast.py
  python src\sync_stock_fast.py --dry-run
  python src\sync_stock_fast.py --limit 20

Лог пишеться у:
  D:\FISH\fish-sync\logs\stock_sync_YYYYMMDD_HHMMSS.log
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
LOG_DIR = ROOT / "logs"
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Швидка синхронізація залишків УкрСклад → Horoshop")
    ap.add_argument("--dry-run", action="store_true", help="Показати payload без POST")
    ap.add_argument("--limit", type=int, default=None, help="Обмежити кількість товарів (для тесту)")
    ap.add_argument("--skip-snapshot", action="store_true", help="Пропустити копіювання БД (якщо вже є)")
    args = ap.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"stock_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    started = datetime.now()
    report: dict = {"started": started.isoformat(), "steps": {}}

    def step(name: str, data: object) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {name}: {json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else data}")

    try:
        # 1. Snapshot УкрСкладу
        from ukrsklad import take_snapshot, dump_all
        if not args.skip_snapshot:
            take_snapshot()
            step("snapshot", "OK — сталась копія Sklad.tcb")
        else:
            step("snapshot", "пропущено (--skip-snapshot)")

        # 2. Витягнути products.json
        stats = dump_all(ROOT / "data" / "products.json", refresh_snapshot=False)
        report["steps"]["extract"] = stats
        step("extract", stats)

        # 3. Group models (потрібно для build_canonical_products)
        import group_models
        group_models.main()
        step("group", "OK")

        # 4. Синхронізація в Horoshop (тільки ціни і залишки)
        import horoshop_sync
        sync_stats = horoshop_sync.sync(
            dry_run=args.dry_run,
            limit=args.limit,
            skip_meta=True,   # без AI-описів, фото, характеристик
        )
        report["steps"]["horoshop_sync"] = sync_stats
        step("horoshop_sync", sync_stats)

        report["status"] = "ok"

    except Exception as exc:
        report["status"] = "error"
        report["error"] = str(exc)
        report["traceback"] = traceback.format_exc()
        print(f"[ERROR] {exc}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)

    finished = datetime.now()
    report["finished"] = finished.isoformat()
    report["duration_sec"] = round((finished - started).total_seconds(), 1)

    log_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nЛог: {log_path}")
    print(f"Статус: {report['status']} | Час: {report['duration_sec']}с")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
