# Перенесення fish-sync на новий ноутбук — покрокова інструкція

Дата підготовки: 2026-07-13. Перевірено на реальному встановленні (Python 3.11, Windows).

## 0. Головне правило: однакові літери дисків

**106 скриптів у `src/` мають захардкожений шлях `ROOT = Path(r"D:\FISH\fish-sync")`**,
а 3 скрипти — `F:\FISH_IMAGES`. Це означає: **найпростіший і найнадійніший спосіб** —
відтворити ТОЧНО ТАКУ Ж структуру дисків на новому ноутбуці:

- Проєкт має лежати рівно в `D:\FISH\fish-sync` (диск `D:`).
- Клієнтські фото — рівно в `F:\FISH_IMAGES` (диск `F:`).

Якщо на новому ноутбуці немає фізичного диска D:/F:, можна:
- створити на диску C: папку і призначити їй букву D: через Управління дисками
  (Диспетчер дисків → правою кнопкою на розділ C: → "Змінити букву диска" не підійде,
  краще: підключити папку як диск командою `subst D: C:\FISH` — працює одразу, без
  перезавантаження, але треба виконувати `subst` при кожному старті Windows, або додати
  в автозавантаження);
- **АБО** (довше, але надійніше) — вручну виправити 106+3 захардкожені шляхи. Не рекомендується,
  якщо не плануєте це робити систематично.

Далі інструкція вважає, що ви використовуєте `D:\FISH\fish-sync` і `F:\FISH_IMAGES`.

---

## 1. Передумови на новому ноутбуці

1. **Windows** з правами адміністратора.
2. **Python 3.11** (саме 3.11, не 3.14 — перевірено, що робочий пайплайн використовує
   систему з Python 3.11; `python --version` має показати `3.11.x`).
   Завантажити: https://www.python.org/downloads/release/python-3110/
   При встановленні — обов'язково галочку **"Add python.exe to PATH"**.
3. **Git for Windows**: https://git-scm.com/download/win
4. **УкрСклад7** — має бути встановлений. Без нього не працюватиме синхронізація
   "УкрСклад → Horoshop" (але решта — робота з Horoshop напряму — працюватиме).

   ⚠️ **Шлях до бази РІЗНИЙ залежно від редакції** — на робочому ноуті магазину стоїть
   клієнт-серверна версія (`UkrSklad7C` + `UkrSklad7S`), а не однокористувацька `UkrSklad7`.
   Скрипт `src/ukrsklad.py` шукає базу автоматично (`find_live_db()`): перевіряє
   `UkrSklad7S`, `UkrSklad7C`, `UkrSklad7` у `C:\ProgramData` (+ `D:\ProgramData`,
   `C:\Users\Public`) і бере **найбільший** знайдений `Sklad.tcb` — бо в клієнта база
   може бути порожньою заглушкою. **Нічого правити в коді не треба.**

   Перевірити, що знайшлась правильна база:
   ```
   python -c "import sys; sys.path.insert(0,'src'); import ukrsklad as u; print(u.LIVE_DB, u.LIVE_DB.exists())"
   ```
   Якщо база лежить нестандартно — вказати шлях явно в `.env`:
   ```
   UKRSKLAD_DB_PATH=C:\ProgramData\UkrSklad7S\db\Sklad.tcb
   ```
   Знайти всі бази на диску вручну:
   ```powershell
   Get-ChildItem C:\ -Filter Sklad.tcb -Recurse -ErrorAction SilentlyContinue |
     Select-Object FullName, @{N='MB';E={[math]::Round($_.Length/1MB,1)}}, LastWriteTime
   ```

---

## 2. Що скопіювати зі старого ноутбука (НЕ через git)

Репозиторій є на GitHub (`https://github.com/MaxSaiets/Fish.git`), але `.gitignore`
навмисно виключає секрети та важкі бінарні файли. Їх треба перенести вручну
(флешка, зовнішній диск, хмара — як зручно):

| Що копіювати | Звідки (старий ноут) | Куди (новий ноут) | Розмір | Навіщо |
|---|---|---|---|---|
| Секрети | `D:\FISH\fish-sync\.env` | те саме місце | 1 КБ | логіни/паролі Horoshop, API-ключі |
| Токен Telegram-бота | `D:\FISH\fish-sync\src\telegram_bot\config.json` | те саме місце | 1 КБ | токен бота модерації (у git НЕ зберігається — секрет) |
| Firebird-клієнт | `D:\FISH\fish-sync\tmp\fb3x64\` (вся папка) | те саме місце | ~63 МБ | без цього не підключиться до бази УкрСкладу |
| Кеш метаданих (опційно) | `D:\FISH\fish-sync\data\meta_store.sqlite` | те саме місце | — | AI-описи/статуси товарів (можна перегенерувати, але довше) |
| Фото товарів (опційно) | `D:\FISH\fish-sync\public\photos\` | те саме місце | — | вже завантажені фото (можна перезалити з нуля) |
| Клієнтські фото | `F:\FISH_IMAGES\` (вся папка) | те саме місце | ~233 МБ | джерело реальних фото товарів, використовується в кількох скриптах |

**Усі ці файли вже є в zip-пакеті `D:\FISH_TRANSFER.zip`, зібраному на старому ноуті** —
достатньо розпакувати його. Код же тепер краще брати з GitHub (див. розділ 3), бо він
там актуальний і автоматично оновлюється.

**Ніколи не публікуйте `.env` чи `config.json` в git, чат чи будь-де публічно** — там паролі та токени.

---

## 3. Код — з GitHub (актуальний, з авто-оновленням)

Код тепер повністю на GitHub і оновлюється автоматично. Два способи:

**Спосіб А (рекомендований) — свіжий clone:**
```powershell
cd D:\
mkdir FISH
cd FISH
git clone https://github.com/MaxSaiets/Fish.git fish-sync
cd fish-sync
```
Далі поверх клону скопіюй лише СЕКРЕТИ/ДАНІ з zip (розділ 2): `.env`,
`src\telegram_bot\config.json`, `tmp\fb3x64\`, `data\`, і окремо `F:\FISH_IMAGES`.
Вони в git не зберігаються, тому clone їх не приносить — беруться з пакета.

**Спосіб Б — з zip-пакета:**
Розпакуй `D:\FISH_TRANSFER.zip` (папку `fish-sync` → `D:\FISH\fish-sync`,
`FISH_IMAGES` → `F:\FISH_IMAGES`), потім синхронізуй код до останньої версії з GitHub:
```powershell
cd D:\FISH\fish-sync
git fetch origin
git reset --hard origin/main
```
`git reset --hard` чіпає ТІЛЬКИ код (src/docs) — секрети, `.env`, `data`, фото
(вони в .gitignore) лишаються недоторканими. Після цього репозиторій готовий до
авто-оновлення.

> Обидва способи дають однаковий результат: код точно як на GitHub + робочий git,
> який щоразу перед синхронізацією підтягуватиме твої майбутні зміни (див. розділ 8).

---

## 4. Встановити залежності Python

```powershell
cd D:\FISH\fish-sync
python -m pip install --upgrade pip

# Основні
pip install requests python-dotenv fdb openpyxl pillow rapidfuzz openai

# Playwright — потрібен для: імпорту через pricelist (import_parent_brand.py та інші
# fix_*/import_*/enrich_* скрипти), sync_orders.py, sync_content_playwright.py
pip install playwright
playwright install chromium

# Google Gemini SDK (якщо використовуєте GEMINI_API_KEY з .env для AI-описів)
pip install google-generativeai

# Telegram-бот модерації (опційно — на момент 2026-07-13 ще не повністю налаштований,
# TELEGRAM_BOT_TOKEN порожній; можна пропустити, якщо цю функцію не використовуєте)
pip install aiogram==3.13.1

# Планувальник для автозапуску всередині Python (опційно — можна замінити на
# Windows Task Scheduler, розділ 8 нижче)
pip install schedule
```

Перевірка, що все встановилось:

```powershell
python -c "import requests, dotenv, fdb, openpyxl, PIL, rapidfuzz, openai, playwright; print('OK')"
```

Якщо якийсь модуль не знайдено — `pip install <назва>` окремо.

---

## 5. Перевірити `.env`

Відкрити `D:\FISH\fish-sync\.env` (має бути скопійований на кроці 2) і переконатись,
що там є всі ключі (значення — реальні секрети зі старого ноутбука):

```ini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash-lite
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
HOROSHOP_BASE_URL=https://vsedliarybalky.com.ua
HOROSHOP_LOGIN=...
HOROSHOP_PASS=...
HOROSHOP_STOCK_MODE=presence
```

Якщо файлу немає — створити вручну з цими рядками і реальними значеннями
(логін/пароль від адмінки Horoshop, ключі API).

---

## 6. Перевірити Firebird-з'єднання (найчастіше місце поломки)

`src/ukrsklad.py` (рядок 22) містить:

```python
FBCLIENT = Path(r"D:\FISH\fish-sync\tmp\fb3x64\fbclient.dll")
LIVE_DB = Path(r"C:\ProgramData\UkrSklad7\db\Sklad.tcb")
```

Якщо на новому ноутбуці проєкт лежить рівно в `D:\FISH\fish-sync` (як в розділі 0) —
нічого правити не треба. Якщо шлях інший — відредагувати ці два рядки вручну.

Тест з'єднання:

```powershell
python -c "from src.ukrsklad import fetch_products; print(len(fetch_products()), 'товарів прочитано')"
```

(якщо функція називається інакше — просто запустити `python src\ukrsklad.py` напряму,
якщо у файлі є `if __name__ == "__main__"` блок; або дивитись README біля коду).

Типові помилки тут (з GUIDE.md розділу 19):
- **`fbclient not found`** → перевірити, що `tmp\fb3x64\fbclient.dll` реально скопійований (крок 2).
- **`database is currently in use / DB locked`** → УкрСклад7 має бути закритий, або
  скрипт сам знімає снапшот (`tmp\sklad_snapshot.fdb`) — перевірити права на запис у `tmp\`.
- **`Жива БД не знайдена`** → УкрСклад7 не встановлений або база в іншому місці —
  звірити `C:\ProgramData\UkrSklad7\db\Sklad.tcb`.

---

## 7. Тестовий прогін (нічого не змінює в Horoshop)

```powershell
cd D:\FISH\fish-sync
python src\horoshop_sync.py --dry-run --limit 5
```

Якщо це відпрацювало без помилок і показало 5 товарів — з'єднання з Horoshop і
УкрСкладом працює, можна переходити до реальних команд з GUIDE.md (розділ 5 "Щоденна
робота — команди": `python src\run_pipeline.py`, `python src\sync_stock_fast.py` тощо).

---

## 8. Автозапуск (обов'язково, якщо цей ноутбук — основний, з УкрСкладом)

На старому ноутбуці реально налаштовані (перевірено `Get-ScheduledTask`) 2 задачі:

| Задача | Скрипт | Було | Стало на новому ноутбуці |
|---|---|---|---|
| `UkrSkladToHoroshop_StockSync` | `src\sync_stock_playwright.py` | щогодини, **вимкнена** | кожні **2 години**, увімкнена |
| `HoroshopOrders_ToUkrSklad` | `src\sync_orders.py` | щогодини, **вимкнена** | щогодини, увімкнена |

Обидва скрипти вже "щадні" по запитах — вони НЕ ходять в Horoshop окремим
запитом на кожен товар, а роблять **один пакетний імпорт файлом** (Playwright
відкриває сторінку імпорту, вантажить один XLS з усіма товарами, тисне
"Завантажити") — це 5-10 HTTP-звернень за прогін, не тисячі. Тому навіть
щогодинний запуск безпечний. Інтервал для синхронізації залишків все одно
розтягнутий до 2 годин — додатковий запас обережності; замовлення лишені
щогодини, бо затримка тут напряму впливає на реальні відвантаження
(перепродаж товару, якого вже нема).

**Авто-оновлення коду вбудоване:** задачі запускаються не напряму, а через
обгортку `docs\run_task.ps1`, яка перед кожною синхронізацією робить безпечний
`git pull` (тільки чистий fast-forward; якщо офлайн або є розбіжності — просто
працює на наявному коді, синхронізація не падає). Тобто коли ти покращуєш
скрипти на своєму ПК і пушиш у GitHub — цей робочий ноут САМ підтягне зміни
перед наступним запуском. Нічого копіювати вручну не треба.

**Встановити на новому ноутбуці одним скриптом** (портативний — сам визначає
шлях до Python і поточного користувача, нічого не хардкодить):

```powershell
cd D:\FISH\fish-sync
powershell -ExecutionPolicy Bypass -File docs\setup_scheduled_tasks.ps1
```

Перевірити, що задачі увімкнені і на місці:

```powershell
Get-ScheduledTask -TaskName "UkrSkladToHoroshop_StockSync","HoroshopOrders_ToUkrSklad" | Select-Object TaskName, State
```

**КРИТИЧНО — уникнути подвійної обробки замовлень:** якщо старий ноутбук і
далі іноді вмикається і на ньому Windows теж намагається запускати ці задачі
(навіть у стані Disabled, після ручного `Enable-ScheduledTask` хтось міг їх
увімкнути) — замовлення можуть обробитись ДВІЧІ (дублі списання зі складу),
або два ноутбуки одночасно почнуть заливати ціни в Horoshop. Тому, коли новий
ноутбук підтверджено працює:

```powershell
# На СТАРОМУ ноутбуці — вимкнути назавжди, щоб не було конфлікту
Disable-ScheduledTask -TaskName "UkrSkladToHoroshop_StockSync"
Disable-ScheduledTask -TaskName "HoroshopOrders_ToUkrSklad"
```

---

## 9. Чек-лист "все працює"

- [ ] `python --version` → 3.11.x
- [ ] `git clone` (або копія папки) в `D:\FISH\fish-sync`
- [ ] `.env` на місці, з реальними секретами
- [ ] `tmp\fb3x64\fbclient.dll` на місці
- [ ] `F:\FISH_IMAGES` на місці (якщо потрібні клієнтські фото)
- [ ] `pip install` з розділу 4 пройшов без помилок
- [ ] `playwright install chromium` виконано
- [ ] `python -c "import requests, dotenv, fdb, openpyxl, PIL, rapidfuzz, openai, playwright; print('OK')"` → OK
- [ ] `python src\horoshop_sync.py --dry-run --limit 5` → показує товари, без помилок
- [ ] (якщо потрібен УкрСклад) читання Firebird працює без `fbclient not found`
- [ ] `docs\setup_scheduled_tasks.ps1` виконано, обидві задачі `State = Ready`
- [ ] на старому ноутбуці ці ж 2 задачі вимкнені (`Disable-ScheduledTask`), щоб не дублювались

Якщо всі пункти пройдені — середовище повністю відтворене, можна працювати як на
старому ноутбуці.

---

## 9.1 Як твої майбутні зміни автоматично потраплять на робочий ноут

Цикл авто-оновлення працює так:

1. Ти (або Claude) щось покращуєш у коді на будь-якому ПК, де є цей проєкт.
2. Пушиш зміни в GitHub:
   ```powershell
   cd D:\FISH\fish-sync
   git add -A
   git commit -m "опис змін"
   git push
   ```
3. Робочий ноут (з УкрСкладом) перед КОЖНОЮ синхронізацією сам робить `git pull`
   (через `run_task.ps1`) — і бере твій свіжий код автоматично. Руками нічого
   копіювати чи переносити не треба.

**Важливо про секрети:** `.env` і `src\telegram_bot\config.json` НІКОЛИ не йдуть
у git (вони в `.gitignore`). Вони лишаються локальними на кожному ПК. Тобто через
GitHub оновлюється тільки КОД, а паролі/токени — ні. Це навмисно і безпечно.

---

## Швидкий старт: що сказати Claude Code на новому ноутбуці

Після встановлення Claude Code на новому ноутбуці й входу в акаунт, відкрити
термінал у папці, де буде проєкт (наприклад `D:\FISH`), і написати Claude
приблизно так — далі агент сам пройде по цьому файлу:

> Постав fish-sync на цей ноутбук за інструкцією
> `docs\SETUP_NEW_MACHINE.md` з репозиторію `https://github.com/MaxSaiets/Fish.git`.
> Спочатку сам зроби `git clone`, встанови залежності, а потім скажи мені
> точний список файлів/папок, які я маю вручну скопіювати зі старого ноутбука
> (через флешку чи Google Drive) — секрети `.env`, `tmp\fb3x64\`,
> `F:\FISH_IMAGES`. Коли скопіюю — постав автозапуск через
> `docs\setup_scheduled_tasks.ps1` і прожени чек-лист з кінця файлу.
