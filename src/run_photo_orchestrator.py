"""
run_photo_orchestrator.py

Автономний оркестратор фото-наповнення Horoshop.

Тримає два етапи в роботі:
  1. mass_photo_pipeline.py  — пошук/завантаження/обробка фото з інтернету
     (запускається окремо як фоновий процес; цей оркестратор його НЕ керує,
      лише періодично заливає те, що вже оброблено).
  2. horoshop_bulk_photo_uploader.py — заливка готових фото в Horoshop.

Цей скрипт у циклі викликає uploader (drain) кожні N секунд, поки в
mass-photo-utility з'являються нові файли. Має власний resume через
checkpoint uploader-а.

Запуск:
    python src/run_photo_orchestrator.py --interval 180 --concurrency 4
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
PY = ROOT / ".venv" / "Scripts" / "python.exe"
UPLOADER = ROOT / "src" / "horoshop_bulk_photo_uploader.py"
UTILITY_DIR = ROOT / "public" / "mass-photo-utility"
BULK_CP = ROOT / "data" / "horoshop_bulk_upload_checkpoint.json"


def count_utility() -> int:
    return len(list(UTILITY_DIR.glob("*@gallery_common.jpg")))


def count_done() -> int:
    if BULK_CP.exists():
        try:
            return len(json.loads(BULK_CP.read_text("utf-8")).get("done", []))
        except Exception:
            return 0
    return 0


def run_uploader(concurrency: int, clean_gallery: bool) -> None:
    args = [str(PY), "-u", str(UPLOADER), "--concurrency", str(concurrency)]
    if clean_gallery:
        args.append("--clean-gallery")
    subprocess.run(args, cwd=str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=180, help="seconds between drains")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--clean-gallery", action="store_true", default=True)
    ap.add_argument("--max-idle-rounds", type=int, default=20,
                    help="stop after this many rounds with no new uploads")
    args = ap.parse_args()

    print(f"Orchestrator start. interval={args.interval}s concurrency={args.concurrency}")
    idle = 0
    last_done = count_done()

    while True:
        util = count_utility()
        done = count_done()
        pending = util - done
        print(f"\n[{time.strftime('%H:%M:%S')}] utility={util} done={done} pending~={pending}")

        if pending > 0:
            run_uploader(args.concurrency, args.clean_gallery)
            new_done = count_done()
            if new_done > last_done:
                idle = 0
                last_done = new_done
            else:
                idle += 1
        else:
            idle += 1
            print("  nothing pending")

        if idle >= args.max_idle_rounds:
            print(f"\nNo progress for {idle} rounds. Stopping orchestrator.")
            print(f"Final: done={count_done()} utility={count_utility()}")
            break

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
