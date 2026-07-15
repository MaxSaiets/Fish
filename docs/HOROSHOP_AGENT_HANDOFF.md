# Horoshop Agent Handoff

Цей документ потрібен для наступного агента або нейронки, яка має продовжувати наповнення магазину `vsedliarybalky.com.ua`.

## Контекст

- Робоча папка: `D:\FISH\fish-sync`
- Вітрина: `https://vsedliarybalky.com.ua/`
- Адмін-гайд магазину: `https://vsedliarybalky.com.ua/edit/`
- Облікові дані зберігаються локально в `.env`. Не друкувати їх у чат і не комітити.
- Фото з архівів клієнта лежать у `F:\FISH_IMAGES`; розпаковані файли в `F:\FISH_IMAGES\_extracted`.

## Безпечна робота з джерелами

- Для товарів першочергово використовувати фото з `F:\FISH_IMAGES`, бо це клієнтські архіви.
- Якщо фото немає, можна використовувати тільки зображення з відкритою ліцензією або офіційно надані виробником/постачальником.
- Не використовувати watermarked-фото, competitor scraping, фото з ліцензією `ND` для обрізки/color correction або “маскування” авторства.
- Відгуки не вигадувати як реальні. Для демо можна писати тільки явно позначені демо-відгуки.

## Авторизація

Скрипти читають `.env` з такими ключами:

```env
HOROSHOP_BASE_URL=https://vsedliarybalky.com.ua
HOROSHOP_LOGIN=...
HOROSHOP_PASS=...
```

Програмний логін:

```http
POST /core-api/admin/security/login
Content-Type: application/json

{"login":"...","password":"..."}
```

Завантаження зображень:

```http
POST /core-api/admin/app-json/upload-image
multipart/form-data: file=<image>
```

## Стилі, логотип, кольори

Головний генератор CSS:

```powershell
python src\generate_brand_overrides.py
```

Пуш CSS у legacy CSS editor Хорошопу:

```powershell
python src\push_horoshop_client_css.py
```

Згенерований файл: `D:\FISH\brand_override_live.css`.

Поточні бренд-налаштування:

- Header: `#0C1C2A`
- Button/accent: `#D97706`
- Text on dark: `#FFFFFF`
- Text on light: `#1E293B`
- Out-of-stock text target: `#94A3B8`
- Поточний логотип завантажений як `logo-vse-dlia-rybalky-tight.png` і підхоплюється через `data/horoshop_site_assets_report.json`.

## Категорії та підкатегорії

Поточний файл стану:

```text
data/horoshop_category_visuals_report.json
```

Стан після виправлення 2026-06-01:

- `118 / 118` категорій мають `cat_real_*` preview-key.
- `39` прев'ю зроблено з клієнтських архівів.
- Решта зроблені з документованих open-stock джерел, які записані в report.
- Для кожної категорії створено окремий файл у `public/site-category-assets-real-no-text`.
- `cat_unique_*` більше не використовувати: це попередній помилковий набір з текстовими оверлеями.

Команди для повного перевипуску категорій:

```powershell
python src\upload_horoshop_category_visuals.py
python src\build_unique_category_previews.py
python src\build_real_category_previews.py
python src\generate_brand_overrides.py
python src\push_horoshop_client_css.py
```

Якщо upload падає через `RemoteDisconnected`, просто перезапустити `build_real_category_previews.py`.

Важливо: головна сторінка Хорошопу показує картинку для великої категорії-блоку. Підкатегорії всередині цього блоку можуть візуально “успадковувати” картинку батька. Унікальні preview для підкатегорій перевіряти на сторінках/списках, де підкатегорія є окремою плиткою або через CSS selectors у `brand_override_live.css`.

## Сторінки сайту

Контентні сторінки заповнюються скриптом:

```powershell
python src\fill_horoshop_content_pages.py
```

Скрипт працює з такими сторінками:

- `/pro-nas/`
- `/oplata-i-dostavka/`
- `/obmin-ta-povernennya/`
- `/kontaktna-informatsiya/`
- `/privacypolicy/`
- `/store-reviews/`

Звіт:

```text
data/horoshop_content_pages_fill_report.json
```

## Блог

SEO-статті створюються так:

```powershell
python src\seed_horoshop_blog_posts.py
```

Звіт:

```text
data/horoshop_blog_seed_report.json
```

У Хорошопі slug іноді містить `{id}`. Для публічної перевірки замінити `{id}` на числовий id сторінки, наприклад `/slug/37/`.

## Товарні фото

Основні скрипти:

```powershell
python src\upload_horoshop_images.py
python src\build_real_photo_backlog.py
```

Пов'язані звіти:

```text
F:\FISH_IMAGES\_extracted\_image_inventory.csv
F:\FISH_IMAGES\_extracted\_image_analysis_report.json
data\real_photo_backlog_20260531.json
```

Поточний стан з минулого аудиту: частина товарів уже має клієнтські фото з архівів, але великий backlog ще потребує точних реальних фото від клієнта/постачальника. Не замінювати його випадковими scraped-зображеннями без ліцензійної підстави.

### Важливо: не використовувати мокові картки

`src\build_all_product_placeholder_utility.py` був помилковим тимчасовим обхідним шляхом і створював текстові демо-картки. Для клієнтського прев'ю/продакшн-наповнення його не запускати. Якщо такі картки вже залиті, їх треба замінювати тільки реальними фото з `F:\FISH_IMAGES`, офіційних медіа виробника/постачальника або відкритих ліцензійних джерел.

Стан після помилкового обходу, який треба виправляти:

- `7908` унікальних демо-карток згенеровано.
- `7276` артикулів Horoshop прийняв через image-import filename API.
- `7006` товарів без реальних архівних фото перезаписані через `--clean-gallery`, щоб унікальна картка стала основним фото.
- `270` товарів із клієнтськими архівними фото відновлені поверх демо-карток через `public\horoshop-image-utility`.
- `35` артикулів мають `/` або `\` у коді; filename-import Horoshop їх не приймає навіть через `%2F`, тому для них потрібен окремий шлях: змінити артикул/alias у магазині або reverse-engineer пряме редагування галереї через admin product form.

Актуальні звіти:

```text
data\horoshop_all_product_placeholder_utility_report.json
data\horoshop_all_product_placeholder_upload_dryrun.json
data\horoshop_all_product_placeholder_clean_upload_report.json
data\horoshop_real_archive_restore_after_placeholders_report.json
```

## Перевірка у браузері

Рекомендовано перевіряти через Playwright MCP або звичайний браузер:

```text
https://vsedliarybalky.com.ua/?codex_verify=YYYYMMDD
https://vsedliarybalky.com.ua/vudylyshcha/?codex_verify=YYYYMMDD
```

Що перевірити:

- логотип не обрізаний;
- header icons та “Вхід” видно на темному фоні;
- банери не містять випадкових/непризначених фото;
- категорійні картинки підтягуються з `cat_real_*`;
- сторінки “Про нас”, “Оплата і доставка”, “Обмін та повернення”, “Контактна інформація”, “Угода користувача” не містять demo-заглушок;
- блог відкривається за реальними URL;
- товарні фото не мають watermark і відповідають товару.

## Типові проблеми

- Python може друкувати warnings про `google_generativeai` або `pywin32.pth`; якщо команда завершується `Exit code: 0`, це шум середовища.
- Хорошоп може закривати з'єднання під час масового upload. Перезапустити скрипт, який має resume.
- Перший `requests.get()` публічної сторінки може повертати challenge. У скриптах це обходиться cookie `challenge_passed`.
- `brand_override_live.css` великий, бо містить багато селекторів і legacy fallback для Хорошопу.

## Мінімальний порядок робіт для нового агента

1. Прочитати `.env` локально, не виводити секрети.
2. Перевірити `data/horoshop_category_visuals_report.json`.
3. Якщо змінюються категорії: запустити `build_real_category_previews.py`, потім generate/push CSS.
4. Якщо змінюються сторінки: запустити `fill_horoshop_content_pages.py`.
5. Якщо змінюється блог: запустити `seed_horoshop_blog_posts.py` і перевірити публічні URL.
6. Якщо додаються товарні фото: працювати від `F:\FISH_IMAGES` або ліцензійно чистих джерел, потім оновлювати імпорт/звіт.
7. Завжди завершувати браузерною перевіркою вітрини.

## Поточні аудити каталогу

Перед імпортом товарних даних запускати:

```powershell
python src\render_horoshop.py
python src\generate_import_xls.py
python src\generate_import_yml.py
python src\generate_import_csv.py
$env:PYTHONPATH='src'; python src\audit_horoshop_title_quality.py
python src\audit_horoshop_description_quality.py
$env:PYTHONPATH='src'; python src\audit_horoshop_filter_quality.py
$env:PYTHONPATH='src'; python src\audit_horoshop_param_quality.py
python src\audit_horoshop_param_distribution.py
```

Очікуваний стан після чистки 2026-06-07:

- `public\horoshop.xml`: `7942` товари
- `public\horoshop_import.yml`: `127` категорій, `7942` товари
- `public\horoshop_import.xlsx`: `7942` товари
- `public\horoshop_import_legacy.csv`: `7942` товари, `206` колонок, розділювач `;`, UTF-8 BOM
- `data\horoshop_title_quality_report.json`: `bad_count = 0`
- `data\horoshop_description_quality_report.json`: `bad_count = 0`
- `data\horoshop_filter_quality_report.json`: `explicitly_noisy_count = 0`, `noisy_value_count = 0`
- `data\horoshop_param_quality_report.json`: `bad_name_count = 0`, `bad_value_count = 0`, `duplicate_group_count = 0`, `low_param_product_pct ≈ 1.3`

`rare_param_count` у filter-аудиті не є автоматичною помилкою: там багато корисних специфічних характеристик для крісел, підсаків, ліхтарів, батарейок тощо. Видаляти їх масово не треба.

## Стан імпорту товарних даних

API-імпорт `/api/catalog/import/` повертав `409 Api module is not available`, тобто модуль API-імпорту товарів не увімкнений для магазину.

Перевірений legacy-екран:

```text
https://vsedliarybalky.com.ua/adminLegacy/data.php?handler=17
```

На ньому є `Імпорт`, але:

- `public\horoshop.xml` через `/adminLegacy/import/promxml.php` отримує відповідь `Файл не был обработан. Проверьте, пожалуйста, корректность данных в файле`.
- `public\horoshop_import.xlsx` через `/adminLegacy/import/pricelist.php` відкриває preview `Імпорт прайсу`, але файл розпізнається некоректно для масового мапінгу. Не натискати `Импортировать`, доки генератор XLSX не адаптований під цей legacy importer або не відкрито новий Vue-мапінг.
- Прямий upload `public\horoshop_import.yml` через `requests` уперся в JS challenge/редирект і не дійшов до preview. Це не доводить, що YML поганий; це означає, що треба тестувати через реальну браузерну сесію або cookie, які проходять захист.
- Додано запасний файл `public\horoshop_import_legacy.csv`. Локальна перевірка показує, що він має 7942 рядки без заголовка і всі 206 колонок читаються окремо. Його треба перевірити у legacy preview перед будь-яким фінальним імпортом.
- Додано safe-preview генератор `src\generate_import_sample_csv.py`. Він створює `public\horoshop_import_sample_5.csv` і `data\horoshop_import_sample_5_report.json`: 5 товарів у наявності, 206 колонок, `;`, UTF-8 BOM. Важливо: legacy `pricelist.php` відхилив CSV з помилкою `Некорректный формат файла. Необходим формат xml, xls, xlsx`.
- Додано safe-preview генератор `src\generate_import_sample_xlsx.py`. Він створює `public\horoshop_import_sample_5.xlsx`. Legacy upload приймає XLSX без format-error, але preview бачить лише `param[0]` і порожній рядок, тобто XLSX фактично не підходить.
- Додано робочий safe-preview генератор `src\generate_import_sample_html_xls.py`. Він створює `public\horoshop_import_sample_5_html.xls` як HTML-таблицю з Excel-розширенням. Legacy preview для нього показав `206` колонок, `7` рядків, артикул `3762`, без error-слів. Звіт: `data\legacy_pricelist_sample5_html_xls_import_report_20260607.json`.
- Додано повний генератор `src\generate_import_html_xls.py`. Він створює `public\horoshop_import_legacy_html.xls`: `7942` товари, `206` колонок, приблизно `26.9 MB`. Локально перший рядок має `206` клітинок. Це поточний найкращий кандидат для legacy preview повного каталогу.
- Важливе обмеження legacy `pricelist.php`: у safe preview dropdown має `71` доступне поле, з них `68` системних каталогових і лише `1` тестова характеристика `TEST_CHAR_DELETE`. Автоматичний mapping-звіт `data\legacy_pricelist_core_mapping_plan_20260607.json` показує, що можна замапити тільки 10 базових колонок: `Артикул`, `Назва(ua)`, `Назва модифікації(ua)`, `Розділ`, `Цена`, `Валюта`, `Відображати`, `Наявність`, `Бренд`, `Опис товару(ua)`.
- `196` характеристичних колонок у цьому legacy importer поки неможливо замапити, бо відповідні поля не присутні в dropdown. Не запускати фінальний імпорт із очікуванням, що характеристики створяться самі.
- Додано список характеристик для створення/перевірки: `data\horoshop_characteristics_to_create_20260607.csv` і `.json`. Там `196` характеристик із кількістю товарів, кількістю унікальних значень, top values, top categories і рекомендацією `filter` або `card_only`.
- Найважливіші характеристики за покриттям: `Тип` (`6449` товарів), `Країна-виробник` (`5782`), `Матеріал` (`4924`), `Призначення` (`4504`), `Колір` (`2918`), `Вага` (`2106`), `Розмір` (`1449`), `Тип насадки` (`1356`), `Діаметр` (`984`), `Довжина` (`957`).
- Safe sample артикули: `3762`, `3759`, `4452`, `3760`, `3761`. Усі в категорії `PVA матеріали та аксесуари / PVA матеріали`, ціна `175`, статус `В наявності`.
- Додатковий аудит шаблону товару 2026-06-07: пряма сторінка `https://vsedliarybalky.com.ua/adminLegacy/forms/handlers.php?edit=381` показала `78` параметрів шаблону `КАТАЛОГ: Товар`. Звіт: `data\admin_template_381_params_20260607.json`.
- Порівняння імпортних характеристик із реальними параметрами шаблону: `data\import_vs_template_381_compare_20260607.json` і `.csv`. Із `196` характеристик каталогу збігаються `64`, відсутні або не збігаються за назвою `132`, у шаблоні є `12` невикористаних параметрів.
- Додано безпечніший matched-only файл `public\horoshop_import_template381_matched_only_html.xls`: `7942` товари, `74` колонки, з них `64` характеристики, які вже існують у шаблоні Horoshop. Маніфест: `data\template381_matched_only_import_manifest_20260607.json`.
- Важливо: matched-only XLS є кандидатом для наступного preview. Його не імпортувати фінально без перевірки мапінгу в `pricelist.php` і підтвердження користувача.
- Додано хвильовий план відсутніх характеристик: `data\missing_characteristics_wave_plan_20260607.json` і `.csv`. Із `132` відсутніх характеристик критичні для фільтрів тільки `4`: `Матеріал бланка`, `Сегмент`, `Вид`, `Комплектація`; ще `5` нішевих фільтрових; `123` рідкісні поля краще не виводити у фільтри автоматично.
- Додано план фільтрів за сімействами категорій: `data\category_family_filter_plan_20260607.json` і `.csv`. Там `15` сімейств каталогу, `84` рекомендовані фільтри з достатнім покриттям, `21` поле тільки для картки до кращого наповнення, `17` полів пропустити.
- Додано малий matched-only safe sample: `public\horoshop_import_sample_5_template381_matched_only_html.xls`. Це `5` товарів, `74` колонки, `64` характеристики, які вже існують у шаблоні. Звіт: `data\horoshop_import_sample_5_template381_matched_only_report.json`.
- Додано mapping-план для matched-only sample: `data\template381_matched_only_mapping_plan_20260607.json` і `.csv`. Там `10` базових колонок і `64` характеристичні колонки з назвами, alias та id параметрів шаблону.
- Додано план створення перших відсутніх характеристик: `data\characteristics_creation_wave1_2_plan_20260607.json` і `.csv`. У першій хвилі: `Матеріал бланка`, `Сегмент`, `Вид`, `Комплектація`. У другій хвилі: `Конструкція`, `Форма грузила`, `Аромат/варіант`, `Вид монтажу`, `Джерело живлення`.
- Додано генератор повного matched-only файлу: `src\generate_import_matched_only_html_xls.py`. Поточний `public\horoshop_import_template381_matched_only_html.xls` має `7942` товари, `74` колонки, `64` matched-характеристики. Контроль: header `74` клітинки, рядків із заголовком `7943`, manifest збігається.
- У `src\horoshop_catalog.py` додано обережне enrichment-правило для очевидних параметрів: `swivel` отримує `Тип`, `Матеріал`, `Призначення`; `float` отримує `Тип`, `Призначення`, а `Вага` тільки якщо вона явно є в назві (`2gr`, `10+2gr` тощо). Після цього `low_param_product_count` зменшився зі `103` до `97`, `bad_name_count = 0`, `bad_value_count = 0`, `duplicate_group_count = 0`.
- Додано triage низькопараметричних товарів: `data\low_param_products_triage_20260607.json` і `data\low_param_products_triage_by_parent_20260607.csv`. Найбільші групи для наступних batch-правил: `Все для монтажу / карабіни вертлюги та кільця` (`12`) і `Херабуна / поплавки` (`11`).

Безпечний наступний крок: або знайти/увімкнути імпортний механізм, який бачить характеристики, або спершу створити потрібні характеристики в Horoshop і повторити safe preview. Legacy `pricelist.php` можна використати для оновлення базових полів і наявності, але не для повного імпорту характеристик у поточному стані. Масовий фінальний імпорт не запускати без підтвердження.

## Свіжа live-перевірка 2026-06-07

Команди:

```powershell
python src\audit_horoshop_live_storefront.py --product-limit 160 --concurrency 8 --timeout 60 --report data\horoshop_live_storefront_audit_20260607_after_param_rules.json
python src\audit_live_product_media.py --limit 700 --concurrency 12 --timeout 60 --report data\live_product_media_audit_20260607_sample700.json
```

Результат:

- меню: старих назв немає, очікувані назви присутні;
- головна: `31` image-сигнал, каталог і кошик є;
- товари: `160 / 160` перевірених сторінок без помилок;
- фото товарів: `700 / 700` перевірених товарів мають gallery-фото, `missing = 0`;
- браузерна перевірка головної: видимих `no-photo` на категорійних плитках `0`, “Мій кошик” і “Вхід” білі на темному фоні.
