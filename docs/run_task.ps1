<#
Обгортка для запланованих задач із АВТО-ОНОВЛЕННЯМ коду з GitHub.
Перед запуском python-скрипта робить безпечний `git pull` (тільки чистий
fast-forward; якщо офлайн або є розбіжності — просто пропускає і працює
на наявному коді, синхронізація НЕ падає).

Виклик:
  powershell -ExecutionPolicy Bypass -File docs\run_task.ps1 -Script "src\sync_stock_playwright.py"
#>
param(
    [Parameter(Mandatory=$true)][string]$Script,
    [string]$ScriptArgs = ""
)

$root = "D:\FISH\fish-sync"
Set-Location $root

# --- авто-оновлення коду (best-effort, ніколи не валить задачу) ---
try {
    git fetch --quiet 2>$null
    git pull --ff-only --quiet 2>$null
} catch {
    # офлайн / розбіжності — ігноруємо, працюємо на наявному коді
}

# --- запуск самого завдання ---
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { Write-Error "python не знайдено в PATH"; exit 1 }

if ($ScriptArgs) {
    & $py "$root\$Script" $ScriptArgs.Split(" ")
} else {
    & $py "$root\$Script"
}
exit $LASTEXITCODE
