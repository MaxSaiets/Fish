# fish-sync

Пайплайн синхронізації **УкрСклад7 → Horoshop / Rozetka / Facebook Catalog**
для магазину «Все для рибалки» (Раково).

## Архітектура

```
┌─────────────────┐
│ UkrSklad7       │  Firebird DB (Sklad.tcb)
│ (Windows app)   │
└────────┬────────┘
         │ snapshot copy
         ▼
┌─────────────────┐    ┌──────────────────┐
│ ukrsklad.py     │───▶│ products.json    │  raw dump (85 SKU)
└─────────────────┘    └────────┬─────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ group_models.py  │  regex parser → parent/variant
                       └────────┬─────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ models.json      │  53 моделі / 81 варіант
                       └────────┬─────────┘
                                │
                                ▼
                       ┌──────────────────┐    ┌──────────────────┐
                       │ meta_store.py    │◄───│ ai_generator.py  │  Gemini 2.5
                       │ SQLite (upsert)  │    │ (parent only)    │  ~22 моделі/день
                       └────────┬─────────┘    └──────────────────┘
                                │ ▲
                                │ │
                       ┌────────┘ └──────┐
                       ▼                  ▼
              ┌──────────────┐   ┌──────────────┐
              │ photo_sync   │   │ telegram_bot │  Aiogram 3
              │ (фото→kods)  │   │ модерація    │  /approve /reject /regen
              └──────┬───────┘   └──────────────┘
                     │
                     ▼
           ┌──────────────────────┐
           │ render_horoshop.py   │
           │ render_rozetka.py    │
           │ render_facebook.py   │
           └──────────┬───────────┘
                      │
                      ▼
           ┌──────────────────────┐
           │ public/              │
           │   horoshop.xml       │
           │   rozetka.xml        │
           │   facebook.xml       │
           │   photos/<kod>/*.jpg │
           └──────────┬───────────┘
                      │ HTTP
                      ▼
           ┌──────────────────────┐
           │ serve.py :8080       │  Horoshop/Rozetka/FB тягнуть фіди звідси
           └──────────────────────┘
```

## Структура проєкту

```
fish-sync/
├── src/
│   ├── ukrsklad.py         # Firebird reader (snapshot + dump)
│   ├── group_models.py     # regex parent/variant grouper
│   ├── meta_store.py       # SQLite store (upsert-safe)
│   ├── ai_generator.py     # Gemini description generator (parent only)
│   ├── photo_sync.py       # photo importer (filename → kod fuzzy match)
│   ├── render_horoshop.py  # Horoshop YML feed
│   ├── render_rozetka.py   # Rozetka YML feed (≥3 params, state=new)
│   ├── render_facebook.py  # Facebook Catalog RSS (g: namespace)
│   ├── telegram_bot.py     # Aiogram 3 moderation bot (+ --simulate)
│   ├── run_pipeline.py     # full-cycle orchestrator (cron-able)
│   └── serve.py            # HTTP-server для public/
├── data/
│   ├── products.json       # raw dump з УкрСкладу
│   ├── models.json         # парсер-результат
│   ├── meta_store.sqlite   # збагачений контент (опис, params, фото-URL)
│   └── photo_overrides.json (опційно, manual map filename→kod)
├── public/                 # ⭐ те, що серверо віддає назовні
│   ├── horoshop.xml
│   ├── rozetka.xml
│   ├── facebook.xml
│   ├── photos/<kod>/<n>.jpg
│   └── static/no-image.jpg
├── fixtures/
│   └── photos/             # симульована папка Олени для тестів
├── logs/
│   └── pipeline_*.log      # звіти кожного прогону
├── tmp/
│   ├── sklad_snapshot.fdb  # снапшот Firebird
│   └── fb3x64/             # x64 fbclient.dll
├── .env                    # API ключі та налаштування
├── scheduler_setup.md      # інструкція з планувальника
└── README.md
```

## Швидкий старт

### 1. Запуск повного циклу один раз

```bash
cd D:\FISH
python fish-sync/src/run_pipeline.py
```

Це зробить:
- зчитає актуальні товари, ціни й залишки з УкрСкладу
- перебудує `products.json` і фіди
- відправить оновлення в Horoshop через API `catalog/import`

### 2. Перевірити що згенерувалось

```bash
ls fish-sync/public/
# horoshop.xml  rozetka.xml  facebook.xml  photos/  static/
```

### 3. Запустити локальний сервер

```bash
python fish-sync/src/serve.py --port 8080
```

Перевірити:
- http://localhost:8080/horoshop.xml
- http://localhost:8080/rozetka.xml
- http://localhost:8080/facebook.xml

### 4. Зробити URL зовнішньо доступним

Поки немає VPS — через ngrok:
```bash
ngrok http 8080
# отримуєш https://abc.ngrok-free.app
```
Цей URL вставляєш у:
- **Horoshop**: Settings → Імпорт товарів → URL → `https://abc.ngrok-free.app/horoshop.xml`
- **Rozetka Marketplace**: Налаштування магазину → URL прайсу → `.../rozetka.xml`
- **Facebook Commerce Manager**: Catalog → Data sources → Add → Use a URL → `.../facebook.xml`

### 5. Cron щогодини

Див. `scheduler_setup.md` (Windows Task Scheduler).

## Окремі компоненти

### Імпорт нових груп товарів з Excel у УкрСклад

Для масового додавання нових товарів з xlsx-експортів є окремий імпортер:

```bash
# Dry-run: лише preview без запису в УкрСклад
python fish-sync/src/import_xlsx_to_ukrsklad.py --dir "C:/Users/sayet/Downloads/Telegram Desktop"

# Реальний запис у live-базу УкрСкладу
python fish-sync/src/import_xlsx_to_ukrsklad.py --dir "C:/Users/sayet/Downloads/Telegram Desktop" --apply
```

Dry-run збереже нормалізований preview у `data/xlsx_import_preview.json`.

Логіка імпорту:
- створює відсутні групи `TIP`
- додає або оновлює товар у `TOVAR_NAME` за `KOD`
- оновлює залишок у `TOVAR_ZAL`
- розкладає товари по нових сімействах для фідів: вудки, волосінь, флюрокарбон, повідці, бойли, поп-ап, зернові, пелетс, мікси, ліквіди, кивки, сигналізатори

Деталі по характеристиках і мапінгу груп: `docs/NEW_PRODUCT_FAMILIES.md`

### AI генерація описів

```bash
python fish-sync/src/ai_generator.py              # всі draft, паузи 2с
python fish-sync/src/ai_generator.py --limit 5    # 5 за раз
python fish-sync/src/ai_generator.py --force      # перегенерувати все
```

⚠ Free tier `gemini-2.5-flash-lite` = **20 запитів/день/проект**.
Для більшого об'єму:
- Підключити білінг (Tier 1) → 1000 RPD
- Або новий Google Cloud project з новим API key

### Імпорт фотографій

```bash
# З папки Олени
python fish-sync/src/photo_sync.py --src "D:/photos_olena"

# Dry-run (без копіювання)
python fish-sync/src/photo_sync.py --src "D:/photos_olena" --dry-run

# Симуляція (тестова папка)
python fish-sync/src/photo_sync.py --simulate

# Очистити перед імпортом
python fish-sync/src/photo_sync.py --src "..." --clear
```

Алгоритм матчу filename → kod:
1. Manual override (`data/photo_overrides.json`)
2. Точний матч stem (`302.jpg` → `302`)
3. Stem без trailing-суфіксу (`Y-5040-240_1.jpg` → `Y-5040-240`)
4. Артикул з крапками (`1693.06.07.jpg`)
5. Чисто цифровий artikul у назві
6. Fuzzy match (rapidfuzz) проти `display_name` парент-моделі (поріг 75)

### Telegram бот для модерації

**Симуляція (без живого Telegram):**
```bash
python fish-sync/src/telegram_bot.py --simulate
> stats
> pending
> next
> approve <parent_key>
> reject <parent_key>
> regen <parent_key>
```

**Реальний бот:**
1. Створити бота через @BotFather, отримати токен
2. У `.env`:
   ```
   TELEGRAM_BOT_TOKEN=12345:AAA...
   TELEGRAM_ADMIN_IDS=123456789,987654321
   ```
3. `python fish-sync/src/telegram_bot.py`

### Workflow модерації

```
draft  ──ai_generator──▶  ai_draft  ──/approve──▶  approved  ──→ йде у фіди
                              │
                              ├──/reject──▶ rejected
                              └──/regen──▶ draft  (наступний AI прогін перегенерує)
```

## .env приклад

```ini
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-1.5-flash
SHOP_DOMAIN=https://vse-dlya-rybalky.com.ua
PUBLIC_BASE_URL=http://localhost:8080
HOROSHOP_BASE_URL=https://shop645299.horoshop.ua
HOROSHOP_LOGIN=api_login
HOROSHOP_PASS=api_password
HOROSHOP_STOCK_MODE=presence
# Якщо у Horoshop увімкнено "Облік залишків на складах", тоді:
# HOROSHOP_STOCK_MODE=residues
# HOROSHOP_WAREHOUSE=Основний склад
TELEGRAM_BOT_TOKEN=
TELEGRAM_ADMIN_IDS=
```

### Оновлення цін і залишків у Horoshop

```bash
# Перевірка без реальних змін
python fish-sync/src/horoshop_sync.py --dry-run --limit 5

# Реальне оновлення всіх товарів
python fish-sync/src/horoshop_sync.py

# Повний цикл: УкрСклад -> products.json -> Horoshop + фіди
python fish-sync/src/run_pipeline.py --skip-ai
```

Режими залишків:
- `HOROSHOP_STOCK_MODE=presence` — якщо на сайті не ввімкнено складський облік, тоді передається статус наявності.
- `HOROSHOP_STOCK_MODE=residues` — якщо в Horoshop увімкнено облік залишків по складах; у цьому випадку обов'язково треба задати `HOROSHOP_WAREHOUSE` як "Назва для синхронізації" складу в Horoshop.

## Поточний стан / TODO

| Етап | Стан |
|---|---|
| УкрСклад → JSON | ✅ 85 SKU |
| Парсинг parent/variant | ✅ 53 моделі / 81 варіант |
| meta_store SQLite | ✅ |
| AI описи (Gemini) | ⚠️ 24/53 (free quota 20/day) |
| Horoshop YML | ✅ 81 offer, 60 picture-тегів |
| Rozetka YML | ✅ 81 offer, ≥3 params/offer |
| Facebook Catalog | ✅ 81 item, g:image_link fallback |
| HTTP-сервер | ✅ serve.py |
| Photo import (fuzzy) | ✅ 100% match на симуляції |
| Telegram бот | ✅ симулятор + реальний (Aiogram 3) |
| Оркестратор run_pipeline.py | ✅ повний цикл за 0.5с |
| Cron Windows Task Scheduler | 📝 інструкція в scheduler_setup.md |
| **Дані з реальної папки Олени** | ⏳ блокер |
| **Білінг Gemini для решти 29 моделей** | ⏳ блокер |
| **Реальний Telegram токен** | ⏳ блокер |
