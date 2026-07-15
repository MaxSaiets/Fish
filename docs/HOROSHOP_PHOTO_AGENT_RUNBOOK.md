# Horoshop Photo Agent Runbook

Цей документ для іншого агента/нейронки, яка має доробити фото категорій і товарів на `vsedliarybalky.com.ua`.

## Головне правило

Не генерувати текстові мок-картки і не заливати випадкові картинки. Товарне фото має бути реальним фото саме цього товару або офіційним/постачальницьким фото моделі. Для категорій можна використовувати реальні тематичні фото без тексту.

Заборонено:

- `src\build_all_product_placeholder_utility.py` для клієнтського прев'ю або продакшн-наповнення.
- Фото з водяними знаками чужих магазинів.
- “Маскування” чужого фото обрізкою або color correction.
- `--clean-gallery`, якщо немає впевненості, що фото точно відповідає товару.

## Робоче середовище

Робоча папка:

```powershell
cd D:\FISH\fish-sync
```

Секрети лежать у `.env`. Їх можна читати локально, але не друкувати в чат:

```env
HOROSHOP_BASE_URL=https://vsedliarybalky.com.ua
HOROSHOP_LOGIN=...
HOROSHOP_PASS=...
```

Клієнтські фото:

```text
F:\FISH_IMAGES
F:\FISH_IMAGES\_extracted
F:\FISH_IMAGES\_extracted\_image_inventory.csv
```

## Як увійти в Horoshop API

Скрипти вже роблять логін автоматично через `.env`.

Ручний API-login, якщо треба перевірити:

```http
POST https://vsedliarybalky.com.ua/core-api/admin/security/login
Content-Type: application/json

{"login":"<HOROSHOP_LOGIN>","password":"<HOROSHOP_PASS>"}
```

Для масового імпорту фото скрипт отримує токени тут:

```http
GET /core-api/admin/jwt/project-jwt/import-metadata
```

Не копіювати `project_jwt` і `cloud_token` у чат або документацію.

## Категорії

Поточний правильний стан:

- `data/horoshop_category_visuals_report.json`
- `118 / 118` категорій мають `cat_real_*`
- локальні файли: `public\site-category-assets-real-no-text`
- CSS пушиться через `D:\FISH\brand_override_live.css`

Як повністю перевипустити категорійні фото без тексту:

```powershell
python src\build_real_category_previews.py
python src\generate_brand_overrides.py
python src\push_horoshop_client_css.py
```

Якщо на головній якась категорія без фото, причина часто в тому, що Horoshop рендерить `noPhoto` SVG. Перевірити в HTML, що є блок:

```html
<div class="categories-unit-image">
  <svg class="categories-unit-img noPhoto">...</svg>
</div>
```

Для таких блоків CSS має містити примусовий розмір:

```css
.categories-unit-w > a .categories-unit-image {
  display:block!important;
  width:180px!important;
  height:164px!important;
  min-height:164px!important;
}
```

Після зміни CSS завжди запускати:

```powershell
python src\generate_brand_overrides.py
python src\push_horoshop_client_css.py
```

## Товари

Поточна проблема:

- Раніше помилково було залито `7006` текстових мок-карток.
- `270` товарів відновлено реальними фото з клієнтських архівів.
- Частина товарів може мати реальні фото з `mass-photo-utility`.
- Решту треба замінити тільки точними реальними фото.

Ремонтний звіт:

```text
data\horoshop_mock_photo_repair_plan_20260601.json
```

### Правильний формат файлів для імпорту

Horoshop прив'язує фото до товару за артикулом у назві файлу:

```text
{article}@gallery_common.jpg
{article}@gallery_common@2.jpg
{article}@gallery_common@3.jpg
```

Приклад:

```text
#001@gallery_common.jpg
1113@gallery_common.jpg
Y-5040-240@gallery_common.jpg
```

Якщо артикул містить `/` або `\`, filename-import може не прийняти файл. Такі товари йдуть в окрему manual-чергу.

### Як підготувати клієнтські фото

Спочатку перевірити, скільки фото мапиться з архівів:

```powershell
python src\photo_sync.py --src F:\FISH_IMAGES\_extracted --dry-run
```

Якщо dry-run нормальний і збіги точні:

```powershell
python src\photo_sync.py --src F:\FISH_IMAGES\_extracted --clear
python src\build_horoshop_image_utility.py
python src\upload_horoshop_images.py --utility-root public\horoshop-image-utility --report data\horoshop_real_archive_upload_report.json --dry-run --timeout 120 --concurrency 8
```

Якщо dry-run приймає файли, тоді тільки для точних клієнтських фото:

```powershell
python src\upload_horoshop_images.py --utility-root public\horoshop-image-utility --report data\horoshop_real_archive_upload_report.json --clean-gallery --timeout 120 --concurrency 4
```

`--clean-gallery` використовувати лише коли фото точно відповідає товару, бо він видаляє стару галерею.

### РОБОЧИЙ масовий пайплайн (знайдено 2026-06-01)

Повністю автоматичний цикл: пошук в інтернеті -> завантаження -> обробка
(автоконтраст + насиченість x1.18 + квадратна обрізка + 1080x1080, без
водяних знаків магазинів) -> заливка в Horoshop.

```powershell
# 1. Пошук+завантаження+обробка фото у public\mass-photo-utility
#    (--dry-run = тільки качає/обробляє, без заливки; має checkpoint+resume)
python src\mass_photo_pipeline.py --dry-run --concurrency 2

# 2. Заливка оброблених фото в Horoshop (check->AWS upload->assign)
python src\horoshop_bulk_photo_uploader.py --clean-gallery --concurrency 4
```

`mass_photo_pipeline.py`:
- бере backlog з `data\real_photo_backlog_20260531.json` (товари без реального фото);
- групує варіанти за назвою щоб не качати дублі;
- **ВАЛІДАЦІЯ РЕЛЕВАНТНОСТІ:** фото приймається лише якщо в його title/source/url
  є слово типу товару (спінінг/воблер/котушка) ТА збігається бренд/модель.
  Це блокує сміття (напр. рендер кімнати чи "Sharkbay Salt" замість спінінга);
- **ДЕТЕКТОР ВОДЯНИХ ЗНАКІВ:** `red_watermark_ratio()` рахує частку насичено-
  червоних пікселів (overlay "Безкоштовна доставка"/"АКЦІЯ"/телефон). >1.3% →
  кандидат пропускається, береться чистіше джерело;
- пріоритет ЧИСТИХ джерел (rozetka/goldencatch/бренд/cdn.27.ua) над prom.ua,
  де продавці клеять текст;
- **БЕЗ банерів-категорій.** Якщо точного бренду не знайдено — береться РЕАЛЬНЕ
  фото цього ТИПУ товару з пулу `public\family-photo-pool\{family}\` (справжній
  спінінг/воблер/котушка), round-robin. Кожен товар має фото з реального життя;
- checkpoint: `data\mass_photo_checkpoint.json`.

**Запуск автономного циклу (обидва у фоні):**
```powershell
python src\mass_photo_pipeline.py --dry-run --concurrency 2   # качає+валідує+обробляє
python src\run_photo_orchestrator.py --interval 180 --concurrency 4  # заливає clean-gallery
```

`horoshop_bulk_photo_uploader.py`:
- checkpoint: `data\horoshop_bulk_upload_checkpoint.json` (resume);
- `--clean-gallery` прибирає стару mock-картку і лишає чисте реальне фото;
- НЕ чіпає 270 архівних фото (вони в `public\horoshop-image-utility`, інша папка).

**КРИТИЧНО — формат assign (інакше "Data integrity violation"):**

API `/api/import-images/assign` потребує НЕ голий upload-item, а ПОВНИЙ
об'єкт check-відповіді (`awsKey, title, mainTitle, handler, parent, param,
projectUuid, sortOrder`) ЗЛИТИЙ з upload-item + оригінальний `filename`:

```python
merged = {**check_data, **upload_item, "filename": filename}
POST /api/import-images/assign
  {"images": [merged], "cleanGallery": <bool>}
```

Старий `upload_horoshop_images.py` слав лише upload-item -> 400 "Data
integrity violation". Це причина чому масова заливка раніше не працювала.

Той самий flow робить admin-сторінка `/edit/products/image-import`
(перетягування файлів). Формат назв: `{article}@gallery_common.jpg`.

### Як заливати знайдені офіційні фото

1. Знайти фото на офіційному сайті бренду/постачальника або у ліцензійно чистому джерелі.
2. Зберегти джерело в окремий report: URL сторінки, URL картинки, артикул, назва товару.
3. Підготувати зображення 1000-1200 px, JPG/WebP без водяних знаків.
4. Покласти у utility-папку з назвою `{article}@gallery_common.jpg`.
5. Запустити dry-run.
6. Якщо Horoshop приймає, завантажити з `--clean-gallery`.

Мінімальний приклад:

```powershell
New-Item -ItemType Directory -Force public\official-photo-utility
Copy-Item "D:\path\real-photo.jpg" "public\official-photo-utility\#001@gallery_common.jpg"
python src\upload_horoshop_images.py --utility-root public\official-photo-utility --report data\official_photo_upload_dryrun.json --dry-run --timeout 120 --concurrency 4
python src\upload_horoshop_images.py --utility-root public\official-photo-utility --report data\official_photo_upload_report.json --clean-gallery --timeout 120 --concurrency 4
```

## Перевірка

Після кожного upload перевірити 3 рівні:

```powershell
python src\audit_live_product_media.py
```

В браузері:

```text
https://vsedliarybalky.com.ua/?codex_verify=YYYYMMDD
https://vsedliarybalky.com.ua/chokhly/?codex_verify=YYYYMMDD
https://vsedliarybalky.com.ua/sylikonova-prymanka-larva-fanatik-3.0-color-001/?codex_verify=YYYYMMDD
```

У HTML товару перевірити, що `<img class="gallery__photo-img">` веде не на стару мокову картку, а на нове реальне фото.

## Порядок роботи для іншої нейронки

1. Прочитати `.env`, не виводити секрети.
2. Прочитати `data\horoshop_mock_photo_repair_plan_20260601.json`.
3. Не запускати placeholder-скрипти.
4. Для категорій запускати тільки `build_real_category_previews.py`, `generate_brand_overrides.py`, `push_horoshop_client_css.py`.
5. Для товарів спершу брати `F:\FISH_IMAGES\_extracted`.
6. Якщо фото немає в архівах, шукати тільки офіційні/постачальницькі/ліцензійні джерела і записувати source URL.
7. Перед upload завжди робити `--dry-run`.
8. `--clean-gallery` тільки для точних фото.
9. Після upload перевіряти live-сторінку товару.
10. У фінальному звіті писати: скільки товарів оновлено, скільки не знайдено, де лежить report.
