"""
Коригувальний перезалив: знаходить товари, яких торкнувся фікс якості
(_sanitize_params: сміття в Розмірі + дубль Тип/Тип-X), і прибирає їх
з data/bulk_char_progress.json, щоб bulk_char_update перезалив їх чистими.

  python src/corrective_rerun.py            # dry-run: лише показати к-сть
  python src/corrective_rerun.py --apply    # прибрати з прогресу (запускати ПІСЛЯ main-run)
потім:
  python src/bulk_char_update.py            # перезаллє прибрані (+ дозаллє решту)
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

PROGRESS = ROOT / "data" / "bulk_char_progress.json"


def build_params(sanitize: bool) -> dict:
    import param_enrichment as pe
    pe.SANITIZE_ENABLED = sanitize
    # horoshop_catalog кешується на рівні модуля? Перезавантажимо для чистоти.
    import horoshop_catalog as hc
    importlib.reload(hc)
    out = {}
    for p in hc.build_canonical_products():
        out[str(p["article"]).strip()] = [(x["name"], str(x.get("value", ""))) for x in (p.get("params") or [])]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    raw = build_params(False)
    clean = build_params(True)
    affected = sorted(a for a in raw if raw.get(a) != clean.get(a))
    print(f"товарів, яких торкнувся фікс якості: {len(affected)}")
    print("приклади:", affected[:10])

    done = set(json.loads(PROGRESS.read_text(encoding="utf-8"))) if PROGRESS.exists() else set()
    to_reset = [a for a in affected if a in done]
    print(f"з них уже залито (треба перезалити): {len(to_reset)}")

    if args.apply:
        new_done = sorted(done - set(affected))
        PROGRESS.write_text(json.dumps(new_done, ensure_ascii=False), encoding="utf-8")
        print(f"прибрано з прогресу {len(done) - len(new_done)}; лишилось done={len(new_done)}")
        print("тепер запусти: python src/bulk_char_update.py")
    else:
        print("(dry-run; для застосування додай --apply ПІСЛЯ завершення main-run)")
    return 0


if __name__ == "__main__":
    sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.exit(main())
