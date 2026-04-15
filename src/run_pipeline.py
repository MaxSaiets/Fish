"""
Оркестратор повного циклу синхронізації.

Етапи:
  1. snapshot — копія Sklad.tcb
  2. extract  — products.json з Firebird
  3. group    — models.json (parent/variant)
  4. import   — meta_store upsert (зберігає AI-контент)
  5. ai       — Gemini для нових parent-моделей (status='draft', best-effort)
  6. render   — horoshop.xml + rozetka.xml + facebook.xml
  7. report   — короткий звіт у stdout + лог-файл

Запуск:
  python src/run_pipeline.py                  # повний цикл
  python src/run_pipeline.py --skip-ai        # без Gemini (наприклад денна квота)
  python src/run_pipeline.py --skip-snapshot  # коли БД вже скопійована

Cron: див. scheduler_setup.md
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


def log_step(name: str, payload: dict | str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] === {name} ===")
    if isinstance(payload, dict):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-snapshot", action="store_true")
    ap.add_argument("--skip-extract", action="store_true")
    ap.add_argument("--skip-group", action="store_true")
    ap.add_argument("--skip-ai", action="store_true")
    ap.add_argument("--ai-limit", type=int, default=20, help="Макс. AI-запитів за прогон (free tier).")
    ap.add_argument("--photos-src", type=Path, default=None, help="Папка з фото для photo_sync")
    ap.add_argument("--skip-horoshop", action="store_true", help="Не синхронізувати Horoshop")
    ap.add_argument("--rebuild-map", action="store_true", help="Пересканувати article→id маппінг Horoshop")
    ap.add_argument("--dry-run", action="store_true", help="Horoshop sync без реальних POST")
    args = ap.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    started = datetime.now()
    report = {"started": started.isoformat(), "steps": {}}

    try:
        # 1. Snapshot + extract
        if not args.skip_extract:
            from ukrsklad import dump_all, take_snapshot
            if not args.skip_snapshot:
                take_snapshot()
                log_step("snapshot", "OK")
            stats = dump_all(ROOT / "data" / "products.json", refresh_snapshot=False)
            report["steps"]["extract"] = stats
            log_step("extract", stats)

        # 2. Group models
        if not args.skip_group:
            import group_models
            group_models.main()
            log_step("group", "OK")

        # 3. Import meta_store
        from meta_store import import_from_models_json
        stats = import_from_models_json(ROOT / "data" / "models.json")
        report["steps"]["meta_store"] = stats
        log_step("meta_store", stats)

        # 4. Photos (опційно)
        if args.photos_src:
            from photo_sync import sync_folder
            stats = sync_folder(args.photos_src, dry_run=False)
            report["steps"]["photos"] = stats
            log_step("photos", stats)

        # 5. AI generation (best-effort, не валимо pipeline якщо квота)
        if not args.skip_ai:
            try:
                import ai_generator
                import sqlite3
                conn = sqlite3.connect(ROOT / "data" / "meta_store.sqlite")
                conn.row_factory = sqlite3.Row
                model = ai_generator.genai.GenerativeModel(ai_generator.MODEL_NAME)
                pending = ai_generator.fetch_pending(conn, force=False, limit=args.ai_limit)
                ok = fail = 0
                for row in pending:
                    pk = row["parent_key"]
                    variants = ai_generator.fetch_variants(conn, pk)
                    try:
                        result = ai_generator.generate_one(model, dict(row), variants)
                        ai_generator.save(conn, pk, result)
                        ok += 1
                        print(f"  ai ✓ {pk}")
                    except Exception as e:
                        fail += 1
                        msg = str(e)[:120]
                        print(f"  ai ✗ {pk} — {msg}")
                        # Якщо денна квота — припиняємо, не марнуємо ретраї
                        if "429" in msg and "PerDay" in msg:
                            print("  ai stopped: daily quota exhausted")
                            break
                conn.close()
                report["steps"]["ai"] = {"ok": ok, "fail": fail, "limit": args.ai_limit}
                log_step("ai", report["steps"]["ai"])
            except Exception as e:
                report["steps"]["ai"] = {"error": str(e)}
                log_step("ai", f"SKIPPED: {e}")

        # 6. Render
        from render_horoshop import render as render_horoshop
        from render_rozetka import render as render_rozetka
        from render_facebook import render as render_facebook
        render_horoshop()
        render_rozetka()
        render_facebook()
        log_step("render", "OK (3 feeds)")

        # 7. Horoshop sync (price + stock via official API)
        if not getattr(args, "skip_horoshop", False):
            try:
                import horoshop_sync
                stats = horoshop_sync.sync(
                    rebuild_map=getattr(args, "rebuild_map", False),
                    dry_run=getattr(args, "dry_run", False),
                )
                report["steps"]["horoshop_sync"] = stats
                log_step("horoshop_sync", stats)
            except Exception as e:
                report["steps"]["horoshop_sync"] = {"error": str(e)}
                log_step("horoshop_sync", f"SKIPPED: {e}")

        report["status"] = "ok"
    except Exception as e:
        report["status"] = "error"
        report["error"] = str(e)
        report["traceback"] = traceback.format_exc()
        log_step("ERROR", report["traceback"])

    finished = datetime.now()
    report["finished"] = finished.isoformat()
    report["duration_sec"] = round((finished - started).total_seconds(), 1)

    log_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport: {log_path}")
    print(f"Status: {report['status']}, duration: {report['duration_sec']}s")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    sys.exit(main())
