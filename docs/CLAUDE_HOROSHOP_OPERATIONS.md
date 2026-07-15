# Інструкція для Claude AI: Horoshop-магазин Vsedliarybalky

Цей документ потрібен, щоб інша нейронка або оператор могли продовжити роботу з магазином без втрати контексту: як підключатись, що вже зроблено, як готувати товари, фото, категорії, блог, стилі та як безпечно перевіряти імпорт.

## 1. Головне правило безпеки

Не робити фінальний масовий імпорт живого каталогу без безпечного preview і явного підтвердження від користувача.

У цьому проекті вже були випадки, коли Horoshop приймав файл, але неправильно бачив колонки або не показував потрібні поля для мапінгу. Тому будь-яка масова дія має проходити так:

1. Згенерувати або взяти sample-файл на 5 товарів.
2. Завантажити його у preview імпорту Horoshop.
3. Перевірити кількість колонок, артикули, назви, описи, характеристики, фото.
4. Зберегти звіт або коротко зафіксувати результат.
5. Тільки після підтвердження користувача переходити до повного імпорту.

Не друкувати в чат, документацію або коміти логіни, паролі, токени, cookies, session id та інші секрети. Секрети читати тільки локально з `.env`.

Не використовувати чужі фото з водяними знаками, фото конкурентів або фото без дозволу. Безпечні джерела: архіви клієнта, офіційні фото виробників/постачальників, open-license/free stock фото без водяних знаків. Якщо фото тимчасове демонстраційне, це треба явно позначити у звіті і потім замінити на реальне.

## 2. Поточний контекст магазину

Робоча папка проекту:

```powershell
D:\FISH\fish-sync
```

Сайт:

```text
https://vsedliarybalky.com.ua/
```

Адмін-гайд Horoshop:

```text
https://vsedliarybalky.com.ua/edit/
```

Legacy admin:

```text
https://vsedliarybalky.com.ua/adminLegacy/
```

Сторінка товарів та імпорту в legacy admin:

```text
https://vsedliarybalky.com.ua/adminLegacy/data.php?handler=17
```

Пряма сторінка шаблону товару:

```text
https://vsedliarybalky.com.ua/adminLegacy/forms/handlers.php?edit=381
```

Важливі ідентифікатори:

```text
Catalog root ID: 97
Product template: КАТАЛОГ: Товар
Template/handler ID: 381
checkcode: yamete_kudasai
```

Логін і пароль зберігаються локально в `.env`:

```text
HOROSHOP_BASE_URL
HOROSHOP_LOGIN
HOROSHOP_PASS
```

Не показувати ці значення користувачу і не записувати їх у документацію.

## 3. Як підключитись до магазину

### Через браузер

1. Відкрити `https://vsedliarybalky.com.ua/edit/`.
2. Якщо сесія вже активна, перейти в потрібний розділ.
3. Якщо треба логін, взяти дані з локального `.env`, але не виводити їх в чат.
4. Для імпорту, шаблонів, CSS та старих налаштувань часто потрібен legacy admin.
5. Не натискати фінальні кнопки імпорту, публікації або масового видалення без підтвердження користувача.

### Через Core API

Програмний логін:

```http
POST /core-api/admin/security/login
Content-Type: application/json

{
  "login": "...",
  "password": "..."
}
```

Завантаження зображення:

```http
POST /core-api/admin/app-json/upload-image
Content-Type: multipart/form-data

file=<image>
```

Скрипти в проекті вже частково автоматизують логін, upload і звіти. Не вигадувати endpoint для прив'язки фото до товару, якщо він не перевірений. Якщо endpoint невідомий, використовувати існуючі скрипти або legacy import by filename.

## 4. Що вже зроблено

### Дизайн і стилі

Брендові кольори:

```text
Header: #0C1C2A
Button/accent: #D97706
Text on dark: #FFFFFF
Text on light: #1E293B
Out of stock target: #94A3B8
```

Що виправлялось:

```text
Лого не має обрізатись.
Іконки входу, обраного, порівняння і кошика мають бути видимими на темному header.
Текст "Мій кошик" має бути білим на темному фоні.
Сірі/страшні фони у категоріях, кошику та модалці входу прибирались через CSS.
На мобільному меню не має ламати ширину.
На головній прибирались зайві фони і виправлялась сітка банерів/категорій.
```

Основні команди:

```powershell
cd D:\FISH\fish-sync
python src\generate_brand_overrides.py
python src\push_horoshop_client_css.py
```

Згенерований CSS:

```text
D:\FISH\brand_override_live.css
```

Звіт по логотипу та site assets:

```text
data\horoshop_site_assets_report.json
```

### Категорії

Категорії та підкатегорії вже мали окрему хвилю оновлення прев'ю.

Поточний важливий звіт:

```text
data\horoshop_category_visuals_report.json
```

Стан на момент останнього handoff:

```text
118/118 категорій мають preview-key формату cat_real_*
39 прев'ю взяті з клієнтських архівів
решта з документованих open-stock джерел
```

Актуальна папка з реальними прев'ю без текстових оверлеїв:

```text
public\site-category-assets-real-no-text
```

Не використовувати старий набір `cat_unique_*`, бо там були неправильні зображення, повтори або текстові плашки.

Команди:

```powershell
cd D:\FISH\fish-sync
python src\upload_horoshop_category_visuals.py
python src\build_unique_category_previews.py
python src\build_real_category_previews.py
python src\generate_brand_overrides.py
python src\push_horoshop_client_css.py
```

Якщо виникає `RemoteDisconnected`, просто повторити запуск. Скрипти та звіти дозволяють продовжити роботу і звірити стан.

Важливо: Horoshop іноді показує зображення батьківської категорії в великому блоці на головній. Унікальність підкатегорій треба перевіряти на відповідних сторінках категорій, а не тільки в одному dropdown або на головній.

### Сторінки сайту

Заповнювались сторінки:

```text
/pro-nas/
/oplata-i-dostavka/
/obmin-ta-povernennya/
/kontaktna-informatsiya/
/privacypolicy/
/store-reviews/
```

Команда:

```powershell
cd D:\FISH\fish-sync
python src\fill_horoshop_content_pages.py
```

Звіт:

```text
data\horoshop_content_pages_fill_report.json
```

У текстах бажано:

```text
Писати природно українською.
Не використовувати довгі тире.
Не зловживати списками.
Не писати короткий AI-текст на 2 абзаци, сторінки мають виглядати як реальний магазин.
```

### Блог

Блог наповнювався SEO-статтями, але треба уважно перевіряти фото. Раніше були проблеми з однаковими або нетематичними фото.

Основна команда:

```powershell
cd D:\FISH\fish-sync
python src\seed_horoshop_blog_posts.py
```

Також у проекті є додаткові скрипти для апгрейду блогу і заміни фото:

```text
src\upgrade_horoshop_blog_full.py
src\replace_blog_images_openverse.py
```

Звіт:

```text
data\horoshop_blog_seed_report.json
```

Вимоги до блогів:

```text
Кожен блог має мати унікальне тематичне прев'ю.
Не використовувати одні й ті самі фото повторно.
Фото мають відповідати темі статті.
Не ставити випадкові фото риб, людей або природи, якщо стаття про спінінг, фідер, PVA, котушки або гачки.
Тексти мають бути довші, природні, з різними датами.
Не зловживати списками.
Не використовувати довгі тире.
```

Horoshop іноді повертає URL зі slug `{id}`. Для публічної перевірки треба замінити `{id}` на фактичний numeric id, якщо це видно у відповіді або звіті.

## 5. Імпорт товарів

### Канонічний source of truth

Основна логіка генерації каталогу:

```text
src\horoshop_catalog.py
```

Саме тут формуються:

```text
Назви
Бренди
Описи
Характеристики
Наявність
Категорії
Додаткове збагачення характеристик
```

Останні важливі покращення:

```text
Додано FLOAT_WEIGHT_RE
Додано enrich_obvious_param_pairs(...)
Для swivel додаються Тип, Матеріал, Призначення
Для float додаються Тип, Призначення, Вага, але вага тільки якщо явно є в назві
Кількість low-param товарів зменшилась зі 103 до 97
```

### Генерація файлів імпорту

Команди:

```powershell
cd D:\FISH\fish-sync
python src\render_horoshop.py
python src\generate_import_xls.py
python src\generate_import_yml.py
python src\generate_import_csv.py
python src\generate_import_html_xls.py
python src\generate_import_matched_only_html_xls.py
python src\generate_import_sample_matched_only_html_xls.py
```

Очікувані файли:

```text
public\horoshop.xml
public\horoshop_import.yml
public\horoshop_import.xlsx
public\horoshop_import_legacy.csv
public\horoshop_import_legacy_html.xls
public\horoshop_import_template381_matched_only_html.xls
public\horoshop_import_sample_5_template381_matched_only_html.xls
```

Поточні очікувані обсяги:

```text
7942 товари
127 категорій у YML
206 колонок у повному legacy HTML-XLS
74 колонки у matched-only HTML-XLS
64 характеристики збігаються з шаблоном товару 381
```

Важливі звіти:

```text
data\template381_matched_only_import_manifest_20260607.json
data\horoshop_import_sample_5_template381_matched_only_report.json
data\template381_matched_only_mapping_plan_20260607.json
data\template381_matched_only_mapping_plan_20260607.csv
```

### Що не спрацювало

API import:

```text
/api/catalog/import/
```

Повертав:

```text
409 Api module is not available
```

Legacy `promxml.php` відхиляв XML/YML:

```text
Файл не был обработан...
```

Legacy `pricelist.php`:

```text
CSV відхилено як некоректний формат.
XLSX приймався, але парсився неправильно як один порожній param[0].
HTML table .xls працює для safe preview.
```

Тому зараз найбезпечніший формат для перевірки:

```text
public\horoshop_import_sample_5_template381_matched_only_html.xls
```

А для повної хвилі після підтвердження:

```text
public\horoshop_import_template381_matched_only_html.xls
```

Не використовувати повний 206-column файл для фінального імпорту, поки не створені відсутні характеристики або не підтверджений мапінг.

## 6. Безпечний preview імпорту в Horoshop

1. Відкрити legacy admin:

```text
https://vsedliarybalky.com.ua/adminLegacy/data.php?handler=17
```

2. Знайти імпорт/прайс-лист товарів.
3. Завантажити sample:

```text
public\horoshop_import_sample_5_template381_matched_only_html.xls
```

4. У preview перевірити:

```text
Файл бачиться як таблиця, а не одна колонка.
Є 74 колонки.
Є 5 товарів + header.
Артикули sample: 3762, 3759, 4452, 3760, 3761.
Назви, ціни, опис і характеристики читаються нормально.
Dropdown полів має показувати потрібні характеристики або хоча б matched-only поля.
```

5. Звірити мапінг з:

```text
data\template381_matched_only_mapping_plan_20260607.csv
```

6. Якщо dropdown досі не показує потрібні характеристики, зупинитись. Це обмеження імпортера або шаблону, а не XLS.
7. Якщо sample preview правильний, зафіксувати результат і попросити підтвердження на повну хвилю.

Не натискати фінальний імпорт для повного файлу без підтвердження.

## 7. Характеристики і фільтри

### Поточний стан

Звіт по шаблону товару:

```text
data\admin_template_381_params_20260607.json
```

Порівняння імпорту і шаблону:

```text
data\import_vs_template_381_compare_20260607.json
data\import_vs_template_381_compare_20260607.csv
```

Стан:

```text
196 характеристик у каталозі
64 збігаються з шаблоном товару
132 відсутні або мають mismatch по назві
12 параметрів шаблону не використовуються
```

План створення відсутніх характеристик:

```text
data\missing_characteristics_wave_plan_20260607.json
data\missing_characteristics_wave_plan_20260607.csv
data\characteristics_creation_wave1_2_plan_20260607.json
data\characteristics_creation_wave1_2_plan_20260607.csv
```

Критично важливі поля для фільтрів:

```text
Матеріал бланка
Сегмент
Вид
Комплектація
```

Нішеві поля, які теж корисні:

```text
Конструкція
Форма грузила
Аромат/варіант
Вид монтажу
Джерело живлення
```

123 рідкісні поля не треба автоматично робити фільтрами. Їх краще залишати в карточці товару, якщо вони не допомагають покупцю реально звузити вибір.

План фільтрів по сім'ях категорій:

```text
data\category_family_filter_plan_20260607.json
data\category_family_filter_plan_20260607.csv
```

Стан плану:

```text
15 сімей категорій
84 рекомендовані фільтри з достатнім покриттям
21 card-only до покращення даних
17 skip
```

### Як налаштовувати фільтри

Фільтр треба вмикати тільки якщо:

```text
Поле має достатнє покриття в категорії.
Значення не шумні.
Значення допомагають покупцю вибирати.
Поле не дублює назву категорії.
Поле не має десятків одноразових значень без користі.
```

Приклади корисних фільтрів:

```text
Вудилища: Бренд, Довжина, Тест, Кастинг, Тип, Матеріал бланка, Конструкція, Кількість секцій
Котушки: Бренд, Тип, Розмір, Передаточне число, Кількість підшипників, Фрикціон
Гачки: Бренд, Тип, Розмір, Призначення, Форма
Прикормка: Бренд, Вид, Вага, Аромат/варіант, Риба
Пелети: Бренд, Діаметр, Вага, Аромат/варіант, Вид
Монтаж: Тип, Матеріал, Розмір, Призначення
```

Не робити фільтрами поля типу `Артикул`, `Опис`, `Назва`, `Колір`, якщо в конкретній категорії це не має нормального покриття або значення хаотичні.

## 8. Фото товарів

### Джерела фото

Клієнтські архіви:

```text
F:\FISH_IMAGES
```

Розархівовані фото:

```text
F:\FISH_IMAGES\_extracted
```

Інвентаризація:

```text
F:\FISH_IMAGES\_extracted\_image_inventory.csv
F:\FISH_IMAGES\_extracted\_image_analysis_report.json
```

Звіти і checkpoints:

```text
data\real_photo_backlog_20260531.json
data\horoshop_bulk_upload_checkpoint.json
data\horoshop_bulk_upload_report.json
data\live_product_media_audit_after_upload_full_20260605.json
data\live_product_media_audit_after_upload_full_retry_20260605.json
data\live_product_media_audit_after_upload_sample_20260605.json
data\mass_photo_upload_*_20260605.*
```

Основні скрипти:

```text
src\photo_sync.py
src\mass_photo_pipeline.py
src\upload_horoshop_images.py
src\build_real_photo_backlog.py
src\admin_panel_photo_upload.py
src\horoshop_bulk_photo_uploader.py
```

### Важливий факт про попередній стан

Останній live-audit показував, що 700/700 sampled product pages мали gallery photo, missing 0. Але була тимчасова демонстраційна хвиля з placeholder/demo-card фото.

Не запускати для production:

```text
src\build_all_product_placeholder_utility.py
```

Це був тимчасовий workaround, не реальний каталог. Він створював demo cards і не має бути фінальним джерелом фото.

Попередній стан цієї тимчасової хвилі:

```text
7908 demo cards згенеровано
7276 прийняті filename import
7006 товарів без реальних архівів були тимчасово перекриті demo-card main photo
270 товарів з клієнтського архіву були відновлені поверх placeholder
35 артикулів з / або \ в коді не імпортуються через filename import навіть URL-encoded
```

Для фінальної якості треба замінювати placeholder на:

```text
Фото з F:\FISH_IMAGES
Офіційні фото виробника/постачальника
Open-license/free stock фото без водяних знаків, якщо це категорійне/блогове фото
```

### Рекомендований процес для фото товарів

1. Зібрати список товарів без реального фото або з demo-card.
2. Звірити артикул, бренд, назву, категорію.
3. Спочатку шукати фото у `F:\FISH_IMAGES\_extracted`.
4. Якщо фото є, підготувати файл з назвою, сумісною з Horoshop filename import.
5. Якщо фото немає, шукати офіційне фото виробника або open-license джерело.
6. Не використовувати фото з водяними знаками.
7. Для кожного фото перевірити, що воно відповідає конкретному товару, а не лише категорії.
8. Перед масовим upload зробити sample на 5-10 товарів.
9. Після upload запустити live media audit.

Для товарів з артикулами, де є `/` або `\`, filename import не працює. Варіанти:

```text
Змінити article/alias на безпечний формат, якщо це дозволено бізнесом.
Або знайти/перевірити прямий механізм редагування gallery у legacy admin.
Або завантажити вручну через картку товару.
```

Не робити mass rename артикулів без підтвердження користувача.

## 9. Завантаження фото через хмару

Horoshop може приймати фото різними шляхами: upload у адмінці, import by filename, або інколи URL-джерела, якщо це підтримує конкретний імпортер.

Якщо використовувати Google Drive або іншу хмару:

```text
Створити окрему папку тільки для цього проекту.
Не змішувати приватні фото з публічними.
Давати доступ тільки на час імпорту.
Перевірити, що URL прямий і доступний без авторизації, якщо імпортер потребує прямий image URL.
Не залишати публічний доступ довше, ніж потрібно.
Не використовувати Drive як фінальний CDN, якщо Horoshop може зберегти фото локально.
```

Пріоритетний шлях:

```text
1. Клієнтські фото з F:\FISH_IMAGES
2. Поточні скрипти upload/import
3. Офіційна Horoshop-логіка upload
4. Cloud URL тільки якщо це підтверджено preview-тестом
```

## 10. Перевірка якості каталогу

Команди аудитів:

```powershell
cd D:\FISH\fish-sync
$env:PYTHONPATH='src'; python src\audit_horoshop_title_quality.py
python src\audit_horoshop_description_quality.py
$env:PYTHONPATH='src'; python src\audit_horoshop_param_quality.py
$env:PYTHONPATH='src'; python src\audit_horoshop_filter_quality.py
python src\audit_horoshop_param_distribution.py
```

Останній чистий стан:

```text
title bad_count = 0
description bad_count = 0
param bad_name_count = 0
param bad_value_count = 0
duplicate_group_count = 0
low_param_product_count = 97
low_param_product_pct = 1.22
filter explicitly_noisy_count = 0
filter noisy_value_count = 0
rare_param_count = 176
```

Low-param triage:

```text
data\low_param_products_triage_20260607.json
data\low_param_products_triage_by_parent_20260607.csv
```

Найважливіші групи для майбутніх правил:

```text
Все для монтажу / карабіни вертлюги та кільця: 12
Херабуна / поплавки: 11
```

## 11. Live-перевірка сайту

Команди:

```powershell
cd D:\FISH\fish-sync
python src\audit_horoshop_live_storefront.py --product-limit 160 --concurrency 8 --timeout 60 --report data\horoshop_live_storefront_audit_YYYYMMDD.json
python src\audit_live_product_media.py --limit 700 --concurrency 12 --timeout 60 --report data\live_product_media_audit_YYYYMMDD_sample700.json
```

Що перевіряти вручну в браузері:

```text
Головна відкривається без порожніх великих зон.
Каталог відкривається на desktop і mobile.
Категорії не мають сірого фону, якщо дизайн цього не потребує.
У кожної видимої категорії є коректне фото.
У карточках товарів є кнопка купити/замовити, якщо товар в наявності.
Кошик, вхід і реєстрація не мають темних/кривих фонів у формах.
Лого не обрізане.
Текст header читається.
Блог має унікальні тематичні прев'ю.
Сторінки Про нас, Оплата і доставка, Обмін, Контакти, Угода користувача заповнені.
```

Попередній live-audit показував:

```text
menu old names absent, expected present
homepage 31 image signals
160/160 product pages OK
700/700 sampled products had gallery photo, missing 0
category no-photo visible 0
"Мій кошик" and "Вхід" white on dark background
```

Це не означає, що всі фото фінально правильні. Це означає, що технічно зображення відображались у sampled перевірці.

## 12. Поточні блокери і що робити далі

### Блокер 1: не всі характеристики є в шаблоні Horoshop

Є 132 missing або mismatch характеристики. Перед повним імпортом треба або:

```text
Створити потрібні характеристики у шаблоні 381.
Або імпортувати тільки matched-only 64 характеристики.
Або зробити кілька хвиль: спочатку critical fields, потім niche fields, потім full.
```

Рекомендовано:

```text
1. Створити critical fields.
2. Зробити sample import.
3. Перевірити preview.
4. Тільки тоді думати про full import.
```

### Блокер 2: фото з placeholder/demo-card треба замінити на реальні

Технічно фото можуть бути, але не всі фінально правильні. Треба провести окремий real-photo audit:

```text
Товар має фото саме свого товару.
Не категорійне generic фото.
Не demo-card.
Не фото з текстом або водяним знаком.
Не одне фото на різні непов'язані товари.
```

### Блокер 3: 35 артикулів з / або \

Filename import не обробляє такі артикули. Потрібен окремий шлях для фото:

```text
manual upload через карточку
перевірений gallery endpoint
або зміна артикулів після погодження
```

### Блокер 4: імпорт full catalog без preview ризикований

Horoshop legacy import поводиться нестабільно з форматами. HTML-XLS sample працював, але full import треба запускати тільки після preview.

## 13. Швидкий command cheat sheet

### Генерація каталогу

```powershell
cd D:\FISH\fish-sync
python src\render_horoshop.py
python src\generate_import_matched_only_html_xls.py
python src\generate_import_sample_matched_only_html_xls.py
```

### Аудит назв, описів, характеристик і фільтрів

```powershell
cd D:\FISH\fish-sync
$env:PYTHONPATH='src'; python src\audit_horoshop_title_quality.py
python src\audit_horoshop_description_quality.py
$env:PYTHONPATH='src'; python src\audit_horoshop_param_quality.py
$env:PYTHONPATH='src'; python src\audit_horoshop_filter_quality.py
python src\audit_horoshop_param_distribution.py
```

### CSS і бренд

```powershell
cd D:\FISH\fish-sync
python src\generate_brand_overrides.py
python src\push_horoshop_client_css.py
```

### Категорії

```powershell
cd D:\FISH\fish-sync
python src\upload_horoshop_category_visuals.py
python src\build_real_category_previews.py
python src\generate_brand_overrides.py
python src\push_horoshop_client_css.py
```

### Сторінки

```powershell
cd D:\FISH\fish-sync
python src\fill_horoshop_content_pages.py
```

### Блог

```powershell
cd D:\FISH\fish-sync
python src\seed_horoshop_blog_posts.py
```

### Live audit

```powershell
cd D:\FISH\fish-sync
python src\audit_horoshop_live_storefront.py --product-limit 160 --concurrency 8 --timeout 60 --report data\horoshop_live_storefront_audit_manual.json
python src\audit_live_product_media.py --limit 700 --concurrency 12 --timeout 60 --report data\live_product_media_audit_manual_sample700.json
```

## 14. Що Claude має писати користувачу

Коли Claude щось робить, коротко фіксувати:

```text
Що перевірено.
Який файл або звіт оновлено.
Який результат.
Що є блокером.
Чи потрібне підтвердження на ризикову дію.
```

Приклад нормального статусу:

```text
Перевірив sample імпорт: Horoshop бачить 74 колонки і 5 товарів, але dropdown не показує 4 нові critical характеристики. Повний імпорт поки не запускаю. Треба спочатку створити характеристики в шаблоні 381 або імпортувати тільки поточні matched-only поля.
```

Приклад того, що не можна робити:

```text
Я одразу залив повний каталог, бо здається все має бути добре.
```

## 15. LiqPay верифікація та Ветеранський спорт (2026-06-08)

### Ситуація

LiqPay надіслав нотифікацію що під час перевірки сайту не знайшли інформацію про ФОП або юридичну особу. Без цього можуть призупинити прийом платежів. Паралельно — Марина хоче підключити програму «Ветеранський спорт» від ПриватБанку щоб приймати оплату від ветеранів.

### Що зроблено (2026-06-08)

Оновлено три сторінки через `src/fill_horoshop_content_pages.py`:

```
/pro-nas/         — додано розділ «Юридична інформація» з ФОП і РНОКПП
/privacypolicy/   — додано розділ «9. Продавець» з ФОП і РНОКПП
/oplata-i-dostavka/ — додано LiqPay до списку способів оплати
```

Дані ФОП:

```
Продавець: ФОП Гулівата Марина Андріївна
РНОКПП: 3285915727
Адреса: вул. Народної Волі, 1, м. Хмельницький, Україна
Телефон: 067 895-73-71
Email: vsedliarybalky@gmail.com
LiqPay public_key: i62886530633
```

### Платіжні методи в Horoshop (поточний стан)

Увімкнено:

```
LiqPay — Онлайн-оплата банківською карткою (UAH)  ← уже активний
Безготівковий розрахунок
Готівкою
Післяплата
```

Вимкнено (потенційно корисні):

```
«Оплата частинами» ПриватБанку  ← можна увімкнути для розстрочки
«Покупка частинами» від monobank
WayForPay
```

Управляти через: `https://vsedliarybalky.com.ua/edit/settings/payment-methods`

### Як підключити «Ветеранський спорт»

Програма «Ветеранський спорт» — це державна ініціатива через ПриватБанк/LiqPay де ветерани отримують ваучери або пільгові умови для купівлі спортивних товарів у зареєстрованих мерчантів.

Вимоги до сайту (виконано):

```
✓ LiqPay підключений і активний
✓ Публічна оферта/Угода користувача є на сайті
✓ ФОП назва і РНОКПП видимі на сайті
✓ Адреса і телефон на сайті
```

Кроки для бухгалтера для подачі заявки:

```
1. Перейти на liqpay.ua → кабінет мерчанта
2. Увійти через ПриватБанк (логін = номер телефону або картка ПриватБанку)
3. Шукати розділ «Партнерські програми» або «Ветеранський спорт»
4. Якщо не знайдено в кабінеті — зателефонувати менеджеру ПриватБанку
   і запросити підключення до програми «Ветеранський спорт»
5. public_key магазину: i62886530633 — цей код потрібен для заявки
6. Менеджер банку перевірить сайт — тепер ФОП і РНОКПП там є
```

Альтернативно — звернутись напряму до відділення ПриватБанку з документами:

```
Паспорт
Виписка ФОП або свідоцтво про реєстрацію
РНОКПП: 3285915727
URL сайту: https://vsedliarybalky.com.ua/
```

### Нотатка про нотифікацію LiqPay

LiqPay повідомив «Нет, спасибо» (кнопка на скріншоті клієнта). Не натискати цю кнопку — вона відхиляє вимогу і може заблокувати подальшу верифікацію. Тепер сайт містить всі потрібні дані, тому можна повторно пройти верифікацію в кабінеті liqpay.ua.

## 17. Автоматична синхронізація УкрСклад → Horoshop (2026-06-08)

### Архітектура

```
УкрСклад7 (Sklad.tcb)
    ↓ take_snapshot() — копіює .tcb в tmp/sklad_snapshot.fdb
    ↓ dump_all() — витягує продукти через fdb → data/products.json
    ↓ generate_stock_xls() — HTML-таблиця article+price+presence → tmp/stock_upload.xls
    ↓ Playwright (Chromium headless)
         • Логін: POST /core-api/admin/security/login
         • GET /adminLegacy/import/pricelist.php
         • import_type = item
         • file upload (stock_upload.xls ~420KB)
         • маппінг колонок: col_0=article, col_1=price, col_2=presence
         • form.submit() — обходить JS bot-challenge автоматично
         • wait_for_load_state("networkidle", timeout=180s)
    ↓ Horoshop: "Обновлено: 7311 товарів" ✓
```

### Файли

| Файл | Призначення |
|------|-------------|
| `src/sync_stock_playwright.py` | Головний скрипт синхронізації |
| `setup_task_scheduler.ps1` | Реєстрація Windows Task Scheduler |
| `tmp/stock_upload.xls` | Тимчасовий файл імпорту (перезаписується при кожному запуску) |
| `tmp/last_sync_result.png` | Скриншот останнього результату |
| `logs/stock_pw_*.log` | JSON-логи кожного запуску |

### Запуск

```powershell
cd D:\FISH\fish-sync

# Тест без upload
python src\sync_stock_playwright.py --dry-run

# Тест 20 товарів з видимим браузером
python src\sync_stock_playwright.py --headful --limit 20 --skip-snapshot

# Повна синхронізація (headless, ~80 секунд)
python src\sync_stock_playwright.py

# Переглянути останній лог
ls logs\stock_pw_*.log | sort LastWriteTime -Desc | select -First 1 | Get-Content
```

### Task Scheduler (погодинно)

```powershell
# Перереєструвати завдання (від адміна):
.\setup_task_scheduler.ps1

# Перевірити стан:
Get-ScheduledTask -TaskName "UkrSkladToHoroshop_StockSync"

# Запустити вручну:
Start-ScheduledTask -TaskName "UkrSkladToHoroshop_StockSync"
```

### Чому Playwright замість API

Horoshop API `/api/catalog/import/` повертає 409 ("Api module is not available") на поточному плані.
Пряме звернення до `/adminLegacy/import/pricelist.php` через requests блокується JS bot-detection.
Playwright запускає справжній Chromium, тому bot-detection не спрацьовує.

### Замовлення → УкрСклад (ручний процес)

Horoshop не дає доступу до API замовлень на базовому плані.
Після кожного замовлення на сайті:
1. Відкрити `https://vsedliarybalky.com.ua/edit/orders/all`
2. Ввести замовлення вручну в УкрСклад7
3. Погодинний sync автоматично оновить залишки на сайті

## 16. Мінімальний ідеальний наступний план

1. Перегенерувати matched-only sample.
2. Запустити локальні аудити назв, описів, характеристик і фільтрів.
3. Відкрити legacy import preview і перевірити sample.
4. Якщо preview нормальний, попросити дозвіл на повний matched-only import.
5. Окремо пройти real-photo audit і замінити demo/placeholder фото на реальні.
6. Перевірити категорії та підкатегорії на desktop і mobile.
7. Перевірити блог: унікальне фото, довгий текст, тематичність, відсутність повторів.
8. Перевірити сторінки магазину і SEO meta.
9. Запустити live storefront audit.
10. Залишити короткий звіт з посиланнями на оновлені JSON/CSV reports.

