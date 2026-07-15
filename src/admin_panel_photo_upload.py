"""
admin_panel_photo_upload.py

Завантажує оброблені фото в Horoshop через admin panel /edit/products/image-import.
Читає файли з mass-photo-utility, кодує в base64, inject в браузер через CDP,
клікає "Видалити наявні зображення перед імпортом" + "Імпортувати зображення".

Вимоги: Chrome з відкритою адмін-панеллю + Playwright або CDP endpoint.

Запуск:
    python src/admin_panel_photo_upload.py --cdp-port 9222 --batch 15
"""
from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
UTILITY_DIR = ROOT / "public" / "mass-photo-utility"
CHECKPOINT_PATH = ROOT / "data" / "admin_panel_upload_checkpoint.json"
REPORT_PATH = ROOT / "data" / "admin_panel_upload_report.json"
ADMIN_URL = "https://vsedliarybalky.com.ua/edit/products/image-import"


def load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text("utf-8"))
    return {"done": [], "failed": []}


def save_checkpoint(cp: dict) -> None:
    CHECKPOINT_PATH.write_text(json.dumps(cp, ensure_ascii=False, indent=2), "utf-8")


def build_inject_js(files: list[tuple[str, bytes]]) -> str:
    """Build JavaScript that injects files into the import page."""
    file_data = []
    for filename, data in files:
        b64 = base64.b64encode(data).decode()
        file_data.append({"name": filename, "data": b64})

    js_files = json.dumps(file_data)
    return f"""
(async function() {{
  const files = {js_files};
  const dt = new DataTransfer();
  for (const f of files) {{
    const binary = atob(f.data);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const blob = new Blob([bytes], {{type: 'image/jpeg'}});
    dt.items.add(new File([blob], f.name, {{type: 'image/jpeg'}}));
  }}
  const inp = document.querySelector('input[type="file"]');
  inp.files = dt.files;
  inp.dispatchEvent(new Event('change', {{bubbles: true}}));
  return 'injected ' + files.length + ' files';
}})()
"""


def build_click_import_js(delete_existing: bool = True) -> str:
    """Click the import button (optionally checking 'delete existing' checkbox)."""
    return f"""
(async function() {{
  // Check "Видалити наявні зображення перед імпортом" if needed
  const cb = document.querySelector('input[type="checkbox"]');
  if (cb && {str(delete_existing).lower()} && !cb.checked) {{
    cb.click();
  }}
  // Wait a moment for validation
  await new Promise(r => setTimeout(r, 1500));
  // Find and click "Імпортувати зображення"
  const btns = Array.from(document.querySelectorAll('button'));
  const importBtn = btns.find(b => b.textContent.includes('Імпортув') || b.textContent.includes('Завантажити'));
  if (importBtn) {{
    importBtn.click();
    return 'clicked import';
  }}
  return 'button not found: ' + btns.map(b=>b.textContent.trim()).join('|');
}})()
"""


def wait_for_result_js() -> str:
    """Wait until import completes and return status."""
    return """
(async function() {
  const maxWait = 60000;
  const start = Date.now();
  while (Date.now() - start < maxWait) {
    await new Promise(r => setTimeout(r, 1000));
    const success = document.querySelector('.success-message, [class*="success"]');
    const result = document.body.innerText;
    if (result.includes('успішно імпортовано') || result.includes('Результат імпорту')) {
      // Count success/fail
      const match = result.match(/(\\d+)\\s+зображень.*успішно/);
      return 'done:' + (match ? match[1] : '?') + ' result:' + result.substring(0, 200);
    }
    if (result.includes('Завантажено') && result.match(/з\\s+\\d+/)) {
      // Still in progress
      continue;
    }
  }
  return 'timeout';
})()
"""


def read_batch(files: list[Path], start: int, size: int) -> list[tuple[str, bytes]]:
    batch = []
    for p in files[start:start + size]:
        data = p.read_bytes()
        batch.append((p.name, data))
    return batch


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=12, help="Files per batch")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-done", action="store_true", default=True)
    ap.add_argument("--delete-existing", action="store_true", default=True)
    args = ap.parse_args()

    all_files = sorted(UTILITY_DIR.glob("*@gallery_common.jpg"))
    print(f"Total processed images: {len(all_files)}")

    cp = load_checkpoint()
    done_set = set(cp.get("done", []))

    if args.skip_done:
        pending = [f for f in all_files if f.name not in done_set]
    else:
        pending = all_files

    print(f"Pending (not yet uploaded): {len(pending)}")
    total_batches = (len(pending) + args.batch - 1) // args.batch
    print(f"Batches of {args.batch}: {total_batches}")
    print()
    print("=" * 60)
    print("INSTRUCTIONS:")
    print("1. Open Chrome to: " + ADMIN_URL)
    print("2. Make sure you are logged in as admin")
    print("3. Run this script from another terminal OR use the")
    print("   generated JS snippets in the browser console")
    print()
    print("For each batch, copy the JS to browser console at:")
    print(ADMIN_URL)
    print("=" * 60)

    if args.dry_run:
        print(f"\n[DRY-RUN] Would upload {len(pending)} images in {total_batches} batches")
        print(f"First batch files:")
        for f in pending[:args.batch]:
            print(f"  {f.name} ({f.stat().st_size // 1024}KB)")
        return

    # Generate JS snippets for each batch
    JS_DIR = ROOT / "tmp" / "upload_batches"
    JS_DIR.mkdir(parents=True, exist_ok=True)

    for i in range(0, len(pending), args.batch):
        batch_files = pending[i:i + args.batch]
        batch_data = [(f.name, f.read_bytes()) for f in batch_files]
        batch_num = i // args.batch + 1

        js = build_inject_js(batch_data)
        js_path = JS_DIR / f"batch_{batch_num:03d}_inject.js"
        js_path.write_text(js, "utf-8")

        click_js = build_click_import_js(args.delete_existing)
        click_path = JS_DIR / f"batch_{batch_num:03d}_click.js"
        click_path.write_text(click_js, "utf-8")

        print(f"Batch {batch_num}/{total_batches}: {len(batch_files)} files")
        for f in batch_files:
            print(f"  {f.name}")
        print(f"  → Inject JS: {js_path}")
        print()

    print(f"\nAll {total_batches} batch JS files generated in: {JS_DIR}")
    print("\nTo use: for each batch_NNN_inject.js, run in browser console,")
    print("then run batch_NNN_click.js, wait for 'успішно імпортовано',")
    print("then reload the page and run next batch.")


if __name__ == "__main__":
    main()
