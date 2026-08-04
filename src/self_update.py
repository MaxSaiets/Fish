# -*- coding: utf-8 -*-
"""
self_update.py — оновлення коду з GitHub для кнопки «📥 Оновити бота».

Навіщо окремий модуль: простий `git pull` на ноуті магазину ПАДАЄ.
Під час роботи змінюються журнали (`data/notified_orders.json`,
`src/telegram_bot/.offset`…). Раніше вони були під git, і коміт, який їх звідти
прибрав, конфліктує з локальними змінами:

    error: Your local changes to the following files would be overwritten by merge

Git скасовує злиття, код лишається старим, а кнопка показує незрозумілу помилку.
Відтворено на тестовому репозиторії 04.08.2026.

Тому: журнали зберігаємо в пам'ять → відкочуємо їх до стану git → тягнемо код →
повертаємо журнали на місце. Дані НЕ втрачаються, бо ми їх повертаємо,
а після цього коміту вони взагалі не відстежуються git-ом.

Використання:
    from self_update import update_code
    res = update_code()      # {"status": "updated"|"uptodate"|"error", "message": ...}
"""
from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Журнали, які пише сама система під час роботи. Їхні локальні зміни
# НІКОЛИ не мають блокувати оновлення коду.
RUNTIME_FILES = [
    "data/notified_orders.json",
    "data/processed_orders.json",
    "data/notify_alerts_state.json",
    "data/bulk_char_progress.json",
    "data/bot_photo_uploads.json",
    "data/bot_admins.json",
    "src/telegram_bot/.offset",
]


def _git(root: Path, *args: str, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _is_tracked(root: Path, path: str) -> bool:
    return _git(root, "ls-files", "--error-unmatch", "--", path).returncode == 0


def _backup_local_changes(root: Path) -> dict:
    """Копіює всі локально змінені файли у backup_local_<дата>/ + повний diff.

    Викликається лише в режимі force. Нічого не видаляє — просто робить копію,
    щоб після скидання правки можна було подивитись і за потреби повернути.
    """
    staged = _git(root, "diff", "--cached", "--name-only").stdout.split()
    unstaged = _git(root, "diff", "--name-only").stdout.split()
    paths = sorted(set(staged) | set(unstaged))
    if not paths:
        return {"paths": [], "dir": None}

    bdir = root / f"backup_local_{datetime.now():%Y%m%d_%H%M%S}"
    bdir.mkdir(parents=True, exist_ok=True)
    try:
        (bdir / "changes.diff").write_text(_git(root, "diff", "HEAD").stdout or "",
                                           encoding="utf-8")
    except OSError:
        pass
    for rel in paths:
        src = root / rel
        if src.is_file():
            dst = bdir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dst)
            except OSError:
                pass
    return {"paths": paths, "dir": str(bdir)}


def update_code(root: Path | None = None, force: bool = False) -> dict:
    """Тягне свіжий код з GitHub, зберігаючи робочі журнали.

    force=True: якщо оновленню заважають локальні правки КОДУ — спершу зберегти
    їх у backup_local_<дата>/ (копії + diff), потім скинути й оновитись.
    Журнали (замовлення/сповіщення) зберігаються й повертаються В БУДЬ-ЯКОМУ разі —
    саме щоб `git reset` не відкотив список списаних замовлень і те саме
    замовлення не списалося з УкрСкладу вдруге.

    Повертає {"status": "updated" | "uptodate" | "error",
              "message": текст для користувача,
              "commits": [...], "requirements_changed": bool, "backup": {...}}
    """
    root = Path(root or ROOT)
    res: dict = {"status": "error", "message": "", "commits": [], "requirements_changed": False}

    if not (root / ".git").exists():
        res["message"] = f"Це не git-репозиторій: {root}"
        return res

    before = _git(root, "rev-parse", "HEAD").stdout.strip()
    branch = (_git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "main")

    # 1. зберігаємо журнали й прибираємо їх з дороги
    backups: dict[str, bytes] = {}
    for rel in RUNTIME_FILES:
        f = root / rel
        if f.exists():
            try:
                backups[rel] = f.read_bytes()
            except OSError:
                continue
        if _is_tracked(root, rel):
            _git(root, "checkout", "--", rel)          # відкат до стану git

    # 1b. force: зберігаємо локальні правки коду і прибираємо їх з дороги
    self_path = Path(__file__).resolve()
    self_bytes = self_path.read_bytes() if self_path.is_file() else None
    if force:
        backup = _backup_local_changes(root)
        res["backup"] = backup
        if backup["paths"]:
            # journals вже в пам'яті (крок 1). reset прибере і цей файл, якщо його
            # щойно дістали через `git checkout origin/main -- src/self_update.py`
            # (для HEAD він «staged»), тому нижче повертаємо його на місце.
            _git(root, "reset", "--hard", "HEAD")
            if self_bytes and not self_path.exists():
                try:
                    self_path.parent.mkdir(parents=True, exist_ok=True)
                    self_path.write_bytes(self_bytes)
                except OSError:
                    pass

    # 2. тягнемо код
    pull = _git(root, "pull", "--ff-only", "origin", branch)

    # 3. повертаємо журнали (навіть якщо pull не вдався)
    for rel, data in backups.items():
        try:
            f = root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(data)
        except OSError:
            pass

    if pull.returncode != 0:
        err = (pull.stderr or pull.stdout or "").strip()
        blockers = [ln.strip() for ln in err.splitlines()
                    if ln.startswith("\t") or ln.strip().startswith("data/") or
                    ln.strip().startswith("src/")]
        hint = ""
        if "would be overwritten" in err:
            hint = ("\n\nЗаважають ЛОКАЛЬНІ зміни файлів:\n  " + "\n  ".join(blockers[:8]) +
                    "\nЦе не журнали — хтось редагував код на цій машині.\n"
                    "Щоб зберегти ці правки в backup_local_<дата>/ і все одно оновитись:\n"
                    "python src\\self_update.py --force")
        elif "diverged" in err or "non-fast-forward" in err:
            hint = ("\n\nЛокальна гілка розійшлася з GitHub (є місцеві коміти). "
                    "Потрібне ручне злиття.")
        res["message"] = f"Не вдалося оновити код.\n{err[-500:]}{hint}"
        return res

    after = _git(root, "rev-parse", "HEAD").stdout.strip()
    if before == after:
        res["status"] = "uptodate"
        res["message"] = "Уже остання версія — оновлювати нічого."
        return res

    log = _git(root, "log", "--oneline", f"{before}..{after}")
    res["commits"] = [ln for ln in (log.stdout or "").splitlines() if ln.strip()][:10]
    diff = _git(root, "diff", "--name-only", before, after)
    changed = (diff.stdout or "").splitlines()
    res["requirements_changed"] = any("requirements.txt" in c for c in changed)

    res["status"] = "updated"
    res["message"] = (f"Оновлено ({len(changed)} файлів):\n" +
                      "\n".join(f"• {c}" for c in res["commits"]))
    bk = res.get("backup") or {}
    if bk.get("paths"):
        res["message"] += ("\n\n📦 Локальні правки збережено в "
                           f"{Path(bk['dir']).name}/:\n" +
                           "\n".join(f"  • {p}" for p in bk["paths"][:10]) +
                           "\nЖурнали замовлень/сповіщень збережені окремо й на місці.")
    if res["requirements_changed"]:
        res["message"] += ("\n\n⚠️ Змінився requirements.txt — виконай на цій машині:\n"
                           "pip install -r requirements.txt")
    return res


if __name__ == "__main__":
    import sys
    r = update_code(force="--force" in sys.argv)
    print(r["status"])
    print(r["message"])
