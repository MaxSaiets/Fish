"""
photo_watchdog.py

Keeps the full photo run alive unattended for hours:
  - ensures mass_photo_pipeline.py (download/process) is running; restarts if it dies
  - ensures run_photo_orchestrator drains uploads
  - exits when the catalog is fully processed (utility stops growing AND
    all processed images are uploaded) for several consecutive checks.

Run:
    python src/photo_watchdog.py
"""
from __future__ import annotations
import json, subprocess, time, sys
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
PY = ROOT / ".venv" / "Scripts" / "python.exe"
UTIL = ROOT / "public" / "mass-photo-utility"
BULK_CP = ROOT / "data" / "horoshop_bulk_upload_checkpoint.json"
PIPE = ROOT / "src" / "mass_photo_pipeline.py"
UPLOAD = ROOT / "src" / "horoshop_bulk_photo_uploader.py"
PLOG = ROOT / "logs" / "mass_photo_pipeline.log"

def util_count() -> int:
    return len(list(UTIL.glob("*@gallery_common.jpg")))

def done_count() -> int:
    if BULK_CP.exists():
        try: return len(json.loads(BULK_CP.read_text("utf-8")).get("done", []))
        except Exception: return 0
    return 0

def pipe_running(proc) -> bool:
    return proc is not None and proc.poll() is None

def start_pipe():
    return subprocess.Popen(
        [str(PY), "-u", str(PIPE), "--dry-run", "--concurrency", "2"],
        cwd=str(ROOT),
        stdout=open(PLOG, "a", encoding="utf-8"),
        stderr=subprocess.STDOUT)

def run_uploader():
    subprocess.run([str(PY), "-u", str(UPLOAD), "--clean-gallery", "--concurrency", "4"],
                   cwd=str(ROOT),
                   stdout=open(ROOT/"logs"/"bulk_upload.log","a",encoding="utf-8"),
                   stderr=subprocess.STDOUT)

def main():
    print(f"[watchdog] start. done={done_count()} util={util_count()}")
    pipe = start_pipe()
    print(f"[watchdog] pipeline started pid={pipe.pid}")
    stable = 0
    last_util = -1
    while True:
        time.sleep(180)  # 3 min cycle
        # 1) keep pipeline alive
        if not pipe_running(pipe):
            # pipeline exited — if there is still work (util grew recently) restart
            print(f"[watchdog] pipeline exited (code={pipe.poll()}). util={util_count()}")
            # restart unless we've been stable (truly done)
            if stable < 4:
                pipe = start_pipe()
                print(f"[watchdog] pipeline RESTARTED pid={pipe.pid}")
        # 2) drain uploads
        u, d = util_count(), done_count()
        pending = u - d
        print(f"[watchdog] util={u} done={d} pending={pending} pipe_alive={pipe_running(pipe)}")
        if pending > 0:
            run_uploader()
        # 3) completion detection: pipeline dead + nothing pending + util not growing
        if not pipe_running(pipe) and pending <= 0 and u == last_util:
            stable += 1
            print(f"[watchdog] stable {stable}/4")
            if stable >= 4:
                print(f"[watchdog] COMPLETE. final done={done_count()}")
                break
        else:
            stable = 0
        last_util = u

if __name__ == "__main__":
    main()
