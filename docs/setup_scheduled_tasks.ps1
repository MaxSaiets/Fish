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

$projectRoot = "D:\FISH\fish-sync"
if (-not (Test-Path $projectRoot)) {
    Write-Error "Проєкт не знайдено в $projectRoot. Перевірте розділ 0 SETUP_NEW_MACHINE.md (диски D:/F:)."
    exit 1
}

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
        [int]$IntervalHours,
        [string]$StartTime
    )
    # Запуск через обгортку run_task.ps1 — вона робить git pull (авто-оновлення) перед синхронізацією
    $psExe = (Get-Command powershell.exe).Source
    $wrapperArgs = "-ExecutionPolicy Bypass -NonInteractive -File `"$projectRoot\docs\run_task.ps1`" -Script `"$ScriptRelPath`""
    $action = New-ScheduledTaskAction -Execute $psExe -Argument $wrapperArgs -WorkingDirectory $projectRoot
    $trigger = New-ScheduledTaskTrigger -Once -At $StartTime -RepetitionInterval (New-TimeSpan -Hours $IntervalHours) -RepetitionDuration ([TimeSpan]::MaxValue)

    if (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue) {
        Set-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Settings $settings | Out-Null
        Write-Host "Оновлено задачу: $Name (кожні $IntervalHours год)"
    } else {
        Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Settings $settings -User $env:USERNAME | Out-Null
        Write-Host "Створено задачу: $Name (кожні $IntervalHours год)"
    }
    Enable-ScheduledTask -TaskName $Name | Out-Null
}

$today = Get-Date
Set-FishTask -Name "UkrSkladToHoroshop_StockSync" -ScriptRelPath "src\sync_stock_playwright.py" -IntervalHours 2 -StartTime ($today.Date.AddHours(3).AddMinutes(11))
Set-FishTask -Name "HoroshopOrders_ToUkrSklad" -ScriptRelPath "src\sync_orders.py" -IntervalHours 1 -StartTime ($today.Date.AddHours(7).AddMinutes(5))

Write-Host ""
Write-Host "Готово. Перевірка:"
Get-ScheduledTask -TaskName "UkrSkladToHoroshop_StockSync", "HoroshopOrders_ToUkrSklad" | Select-Object TaskName, State
