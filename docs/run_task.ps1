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
    # Runtime-журнали (пишуться під час роботи) раніше були під git і їхні
    # локальні зміни блокували pull. Тепер вони в .gitignore; тут — одноразова
    # міграція: якщо файл ще tracked — зберегти вміст, скинути до HEAD,
    # після pull повернути вміст назад (файл стане untracked/ignored).
    $stateFiles = @(
        "data\notified_orders.json", "data\processed_orders.json",
        "data\notify_alerts_state.json", "data\bulk_char_progress.json",
        "src\telegram_bot\.offset"
    )
    $backups = @{}
    foreach ($f in $stateFiles) {
        git ls-files --error-unmatch -- $f *> $null
        if ($LASTEXITCODE -eq 0 -and (Test-Path $f)) {
            $backups[$f] = [System.IO.File]::ReadAllText("$root\$f")
            git checkout -- $f *> $null
        }
    }
    git fetch --quiet 2>$null
    git pull --ff-only --quiet 2>$null
    foreach ($kv in $backups.GetEnumerator()) {
        [System.IO.File]::WriteAllText("$root\$($kv.Key)", $kv.Value)
    }
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
