# Запуск pipeline щогодини

## Варіант A: Windows Task Scheduler (рекомендовано для прод)

```powershell
# Створити задачу яка щогодини запускає run_pipeline.py
schtasks /Create /SC HOURLY /TN "FishSyncPipeline" ^
  /TR "python D:\FISH\fish-sync\src\run_pipeline.py --skip-ai" ^
  /RL HIGHEST /F

# Подивитись список
schtasks /Query /TN FishSyncPipeline

# Видалити
schtasks /Delete /TN FishSyncPipeline /F
```

Логи кожного прогону пишуться у `D:\FISH\fish-sync\logs\pipeline_YYYYMMDD_HHMMSS.log`.

## Варіант B: Python loop (швидкий dev-режим)

```bash
pip install schedule
python -c "
import schedule, subprocess, time
def job():
    subprocess.run(['python', 'D:/FISH/fish-sync/src/run_pipeline.py', '--skip-ai'])
schedule.every().hour.do(job)
job()  # перший запуск одразу
while True:
    schedule.run_pending()
    time.sleep(30)
"
```

## Варіант C: HTTP-сервер як окремий процес

`run_pipeline.py` оновлює XML-файли у `public/` і відправляє ціни/залишки в Horoshop через API.
`serve.py` віддає XML HTTP-ом — це **окремий процес**, що крутиться 24/7.

```powershell
# Окрема задача яка запускає сервер при старті системи
schtasks /Create /SC ONSTART /TN "FishSyncServer" ^
  /TR "python D:\FISH\fish-sync\src\serve.py --port 8080" ^
  /RU SYSTEM /RL HIGHEST /F
```

Тоді в Horoshop / Rozetka / Facebook Catalog вкажи URL:
- Horoshop: `http://<external-ip>:8080/horoshop.xml`
- Rozetka: `http://<external-ip>:8080/rozetka.xml`
- Facebook: `http://<external-ip>:8080/facebook.xml`

Поки нема статичного IP — ngrok:
```bash
ngrok http 8080
# отримуєш https://abc123.ngrok-free.app — це і є зовнішня адреса
```
