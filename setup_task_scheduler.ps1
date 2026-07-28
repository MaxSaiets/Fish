# setup_task_scheduler.ps1
# Налаштовує Windows Task Scheduler для проєкту FishSync
#
# Запустити один раз від імені адміністратора:
#   Right-click PowerShell → "Run as Administrator"
#   cd D:\FISH\fish-sync
#   .\setup_task_scheduler.ps1
#

# --- Налаштування ---
$WorkingDir  = $PSScriptRoot
$LogDir      = "$WorkingDir\logs"
# Використовуємо pythonw.exe для прихованого (background) виконання без CMD вікон
$PythonExe   = "C:\Users\sayet\AppData\Local\Programs\Python\Python311\pythonw.exe"

if (-not (Test-Path $PythonExe)) {
    # Спробуємо знайти звичайний python і замінити на pythonw
    $found = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($found) {
        $PythonExe = $found -replace "python.exe", "pythonw.exe"
        if (-not (Test-Path $PythonExe)) {
            $PythonExe = $found
            Write-Host "pythonw.exe не знайдено, використано: $PythonExe (вікна можуть з'являтись)" -ForegroundColor Yellow
        } else {
            Write-Host "Pythonw знайдено: $PythonExe"
        }
    } else {
        Write-Error "Python не знайдено"
        exit 1
    }
}

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 60) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -RunOnlyIfNetworkAvailable `
    -StartWhenAvailable

function Register-FishTask {
    param(
        [string]$Name,
        [string]$Script,
        [string]$ArgsList,
        [object]$Trigger,
        [string]$User = "SYSTEM"
    )
    if (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false
        Write-Host "Старе завдання $Name видалено"
    }
    
    $FullArgs = "`"$Script`""
    if ($ArgsList) { $FullArgs += " $ArgsList" }
    
    $Action = New-ScheduledTaskAction -Execute $PythonExe -Argument $FullArgs -WorkingDirectory $WorkingDir
    
    Register-ScheduledTask -TaskName $Name -Action $Action -Trigger $Trigger -Settings $Settings -RunLevel Highest -User $User -Force | Out-Null
    Write-Host "Завдання $Name успішно створено!" -ForegroundColor Green
}

# 1. Синхронізація залишків (щогодини о :00)
$Trigger1 = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration ([TimeSpan]::MaxValue) -At "07:00" -Daily
Register-FishTask -Name "FishSyncStock" -Script "$WorkingDir\src\sync_stock_playwright.py" -ArgsList "" -Trigger $Trigger1

# 2. Синхронізація замовлень (щогодини о :05)
$Trigger2 = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration ([TimeSpan]::MaxValue) -At "07:05" -Daily
Register-FishTask -Name "FishSyncOrders" -Script "$WorkingDir\src\sync_orders.py" -ArgsList "" -Trigger $Trigger2

# 3. Повний цикл з AI (раз на день о 08:00)
$Trigger3 = New-ScheduledTaskTrigger -Daily -At "08:00"
Register-FishTask -Name "FishSyncFullPipeline" -Script "$WorkingDir\src\run_pipeline.py" -ArgsList "" -Trigger $Trigger3

# 4. Локальний сервер для фідів (ONSTART)
$Trigger4 = New-ScheduledTaskTrigger -AtStartup
Register-FishTask -Name "FishSyncServer" -Script "$WorkingDir\src\serve.py" -ArgsList "--port 8080" -Trigger $Trigger4

Write-Host ""
Write-Host "=== УСІ ЗАВДАННЯ СТВОРЕНО УСПІШНО ===" -ForegroundColor Green
Write-Host "Вони будуть виконуватись у фоні без 'чорних вікон'."
