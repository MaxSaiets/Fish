<#
Створює/оновлює 2 заплановані задачі Windows для fish-sync:
  1. UkrSkladToHoroshop_StockSync — залишки/ціни УкрСклад -> Horoshop, кожні 2 години
  2. HoroshopOrders_ToUkrSklad     — замовлення Horoshop -> УкрСклад, щогодини

Портативний: сам визначає шлях до python.exe і поточного користувача,
нічого не хардкодить під конкретний ноутбук/юзера.

Обидві задачі ОДРАЗУ увімкнені (Enabled), запускаються навіть коли ноутбук
не в мережі до цього моменту (StartWhenAvailable), не стартують на батареї
(щоб не саджати заряд, коли ноут не підключений до розетки).

Запуск (з правами звичайного користувача, елевація НЕ потрібна для задач
під поточним юзером):
  cd D:\FISH\fish-sync
  powershell -ExecutionPolicy Bypass -File docs\setup_scheduled_tasks.ps1
#>

$ErrorActionPreference = "Stop"

$pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonPath) {
    Write-Error "python.exe не знайдено в PATH. Встановіть Python 3.11 і переконайтесь, що 'python' викликається з командного рядка."
    exit 1
}
Write-Host "Знайдено Python: $pythonPath"

# Корінь проєкту визначаємо від розташування скрипта (<проєкт>\docs), а не хардкодом —
# інакше на машині з іншим шляхом доводиться правити цей файл локально, і така
# правка згодом блокує git pull (саме це зламало кнопку оновлення 04.08.2026).
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $projectRoot "src"))) {
    Write-Error "Не схоже на корінь проєкту: $projectRoot (немає теки src)."
    exit 1
}
Write-Host "Корінь проєкту: $projectRoot"

$settings = New-ScheduledTaskSettingsSet `
    -DisallowStartIfOnBatteries `
    -StopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

function Set-FishTask {
    param(
        [string]$Name,
        [string]$ScriptRelPath,
        [int]$IntervalHours = 0,
        [int]$IntervalMinutes = 0,
        [string]$ScriptArgs = "",
        [string]$StartTime
    )
    # Запуск через прихований VBS-launcher (run_hidden.vbs), щоб НЕ зʼявлялось вікно
    # PowerShell/CMD. Launcher викликає run_task.ps1 (git pull → python) у фоні.
    $wscript = "$env:SystemRoot\System32\wscript.exe"
    $launchArgs = "//Nologo `"$projectRoot\docs\run_hidden.vbs`" `"$ScriptRelPath`""
    if ($ScriptArgs) { $launchArgs += " `"$ScriptArgs`"" }
    $action = New-ScheduledTaskAction -Execute $wscript -Argument $launchArgs -WorkingDirectory $projectRoot
    if ($IntervalMinutes -gt 0) {
        $repeat = New-TimeSpan -Minutes $IntervalMinutes
    } else {
        $repeat = New-TimeSpan -Hours $IntervalHours
    }
    $trigger = New-ScheduledTaskTrigger -Once -At $StartTime -RepetitionInterval $repeat -RepetitionDuration ([TimeSpan]::MaxValue)

    if (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue) {
        Set-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Settings $settings | Out-Null
        Write-Host "Оновлено задачу: $Name (кожні $IntervalHours год)"
    } else {
        Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Settings $settings -User $env:USERNAME | Out-Null
        Write-Host "Створено задачу: $Name (кожні $IntervalHours год)"
    }
    Enable-ScheduledTask -TaskName $Name | Out-Null
}

# Telegram-бот — окремі налаштування: він працює ПОСТІЙНО, тому
# ExecutionTimeLimit має бути 0 (без ліміту), інакше Планувальник уб'є його
# посеред дня. Батарея теж не має його зупиняти — Марина користується ботом
# із ноутбука без розетки.
function Set-BotTask {
    $name = "FishSyncBot"
    $wscript = "$env:SystemRoot\System32\wscript.exe"
    $launchArgs = "//Nologo `"$projectRoot\docs\run_hidden.vbs`" `"src\telegram_bot.py`""
    $action = New-ScheduledTaskAction -Execute $wscript -Argument $launchArgs -WorkingDirectory $projectRoot
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $botSettings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -RestartCount 99 `
        -RestartInterval (New-TimeSpan -Minutes 5) `
        -ExecutionTimeLimit ([TimeSpan]::Zero)
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        Set-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $botSettings | Out-Null
        Write-Host "Оновлено задачу: $name (автозапуск при вході, без таймліміту)"
    } else {
        Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $botSettings -User $env:USERNAME | Out-Null
        Write-Host "Створено задачу: $name (автозапуск при вході, без таймліміту)"
    }
    Enable-ScheduledTask -TaskName $name | Out-Null
}

# Старі задачі з setup_task_scheduler.ps1 дублюють нові (FishSyncOrders поруч із
# HoroshopOrders_ToUkrSklad = замовлення можуть списатись ДВІЧІ). Вимикаємо.
foreach ($legacy in @("FishSyncStock", "FishSyncOrders", "FishSyncFullPipeline", "FishSyncServer")) {
    $t = Get-ScheduledTask -TaskName $legacy -ErrorAction SilentlyContinue
    if ($t -and $t.State -ne "Disabled") {
        Disable-ScheduledTask -TaskName $legacy | Out-Null
        Write-Host "ВИМКНЕНО стару задачу-дублікат: $legacy" -ForegroundColor Yellow
    }
}

$today = Get-Date
Set-FishTask -Name "UkrSkladToHoroshop_StockSync" -ScriptRelPath "src\sync_stock_playwright.py" -IntervalHours 2 -StartTime ($today.Date.AddHours(3).AddMinutes(11))
Set-FishTask -Name "HoroshopOrders_ToUkrSklad" -ScriptRelPath "src\sync_orders.py" -IntervalHours 1 -StartTime ($today.Date.AddHours(7).AddMinutes(5))
# Сповіщення в Telegram про НОВІ замовлення — кожні 10 хв (потребує src\telegram_bot\config.json)
Set-FishTask -Name "HoroshopOrders_TelegramNotify" -ScriptRelPath "src\notify_new_orders.py" -IntervalMinutes 10 -StartTime ($today.Date.AddHours(0).AddMinutes(2))
Set-BotTask

Write-Host ""
Write-Host "Готово. Перевірка:"
Get-ScheduledTask -TaskName "UkrSkladToHoroshop_StockSync", "HoroshopOrders_ToUkrSklad", `
    "HoroshopOrders_TelegramNotify", "FishSyncBot" -ErrorAction SilentlyContinue |
    Select-Object TaskName, State
Write-Host ""
Write-Host "Повна перевірка ланцюга (нічого не змінює):  python src\diagnose.py"
