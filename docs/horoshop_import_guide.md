# Horoshop Import Guide — Інструкція з імпорту товарів

> Файл для Марини та для Claude. Описує правильний порядок дій для імпорту 7 942 товарів із УкрСклад7 у Horoshop через YML/XML або legacy-friendly CSV.

---

## 1. Загальна схема пайплайну

```
УкрСклад7 (ukrsklad.exe)
  → sync.py            → data/products.json
  → meta_store.py      → data/meta_store.sqlite  (AI-описи, характеристики)
  → horoshop_catalog.py → canonical catalog
  → render_horoshop.py → public/horoshop.xml     (імпорт у Horoshop)
  → generate_import_xls.py → public/horoshop_import.xlsx
  → generate_import_yml.py → public/horoshop_import.yml
  → generate_import_csv.py → public/horoshop_import_legacy.csv
  → generate_import_html_xls.py → public/horoshop_import_legacy_html.xls
  → render_rozetka.py  → public/rozetka.xml      (Rozetka Marketplace)
  → render_facebook.py → public/facebook.xml     (Facebook/Instagram)
```

Файли фідів: `D:\FISH\fish-sync\public\`
Бекап від 25.04.2026: `D:\FISH\fish-sync\public\backup_20260425_1424\`

---

## 2. Порядок першого імпорту в Horoshop (з нуля)

### Крок 1 — Регенерувати фід

```bash
cd D:\FISH\fish-sync
python src\render_horoshop.py
python src\generate_import_xls.py
python src\generate_import_yml.py
python src\generate_import_csv.py
python src\generate_import_html_xls.py
```

Виведе: `OK: written=7942 skipped=0 → public\horoshop.xml`.

Актуальні файли для Horoshop:

- `public\horoshop.xml`
- `public\horoshop_import.yml`
- `public\horoshop_import.xlsx`
- `public\horoshop_import_legacy.csv`
- `public\horoshop_import_legacy_html.xls`

Для старого legacy-екрана `/adminLegacy/import/pricelist.php` поточний робочий формат:

- `public\horoshop_import_sample_5_html.xls` у safe preview дав `206` колонок, `7` рядків і артикул `3762`.
- `public\horoshop_import_sample_5.csv` відхилений як неправильний формат.
- `public\horoshop_import_sample_5.xlsx` приймається, але читається як одна порожня колонка.
- Тому для повного preview використовувати `public\horoshop_import_legacy_html.xls`, але фінальний імпорт запускати тільки після перевірки мапінгу і підтвердження.

### Крок 2 — Перевірити XML на валідність

```python
import xml.etree.ElementTree as ET
ET.parse(r"D:\FISH\fish-sync\public\horoshop.xml")
print("OK")
```

### Крок 3 — Створити категорії в Horoshop (ОБОВ'ЯЗКОВО ПЕРЕД ІМПОРТОМ)

**⚠️ Критично:** Horoshop у режимі "Постачальник" не створює категорії автоматично з YML. Категорії мають існувати заздалегідь.

#### Як створити категорії через браузер (для Claude):

1. Відкрити: `http://shop647643.horoshop.ua/adminLegacy/edit.php?id=addnew&parent=97&handler=4&checkcode=yamete_kudasai`
2. Отримати список шаблонів із `select[name="names[handler]"]`
3. Знайти шаблон **"КАТАЛОГ: Товар"** (зазвичай id=381)
4. Запустити JavaScript у консолі браузера:

```javascript
// Масове створення категорій — виконувати у iframe[0].contentDocument через JS-інструмент
const categories = ["Спінінг", "Вудилища махові", /* ... весь список ... */];

const form = document.querySelector('form');
const createOne = async (name) => {
  const fd = new FormData(form);
  fd.set('names[i18n][3][title]', name.trim());
  fd.set('names[i18n][1][title]', name.trim());
  fd.set('names[handler]', '381'); // ID шаблону "КАТАЛОГ: Товар"
  fd.set('names[inmenu]', '1');
  fd.set('names[insitemap]', '1');
  return fetch('/adminLegacy/save.php', {method:'POST', body: fd});
};

for(let name of categories) {
  await createOne(name);
  await new Promise(r => setTimeout(r, 100));
}
```

**Ключові параметри форми:**
- `names[parent]` = `97` (ID розділу "Каталог" у цьому магазині)
- `names[handler]` = `381` (або актуальний ID шаблону "КАТАЛОГ: Товар")
- `checkcode` = `yamete_kudasai`
- Endpoint: `POST /adminLegacy/save.php`
- **Обов'язково** використовувати `FormData` (не URLSearchParams) — інакше шаблон не передається і категорія не зберігається (save.php повертає 200, але нічого не зберігає)

**Перевірити результат:** `http://shop647643.horoshop.ua/adminLegacy/data.php?handler=4`

#### Список категорій (173 шт.) з `data/categories_list.txt`:

Генерується скриптом:
```bash
python -c "
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
data = json.loads(open(r'D:\FISH\fish-sync\data\products.json', encoding='utf-8').read())
cats = data['categories']
products = data['products']
PLACEHOLDER_TIPS = {1,2,3,4,5}
PLACEHOLDER_NAMES = {'Ваш тип товарів чи послуг','Ваша група товарів чи послуг','Нова група'}
used_tips = {p.get('tip') for p in products if p.get('tip') not in PLACEHOLDER_TIPS}
valid = [c for c in cats if c['name'].strip() not in PLACEHOLDER_NAMES and c['num'] in used_tips]
valid_ids = {c['num'] for c in valid}
for c in valid:
    count = sum(1 for p in products if p.get('tip')==c['num'])
    par = c['parent'] if c['parent'] in valid_ids else 0
    print(f'{c[\"num\"]}|{par}|{c[\"name\"]}|{count}')
" > data\categories_list.txt
```

### Крок 4 — Імпортувати товари в Horoshop

1. Зайти: `http://shop647643.horoshop.ua/edit/products/all`
2. Натиснути **Імпорт** (верхній правий кут)
3. Завантажити файл `D:\FISH\fish-sync\public\horoshop.xml`
4. **Виправити маппінг колонок** — див. Розділ 3 нижче (КРИТИЧНО!)
5. Натиснути **Імпортувати**
6. У діалозі вибрати:
   - Нові товари → **Імпортувати**
   - Існуючі товари → **Оновити**
   - Відсутні товари → **Нічого не робити**
   - Фотографії → **Перезаписати**
7. Натиснути **Почати імпорт**

---

## 3. Маппінг колонок імпорту (КРИТИЧНО — без цього імпорт не працює)

### Чому Horoshop не робить маппінг автоматично?

Horoshop автоматично розпізнає тільки деякі стандартні поля. Поле `<name>` з XML
відображається як "Название модификации(RU)" — і **не маппується автоматично**.
Без правильного маппінгу буде помилка **"не вказано назва товару"** для всіх 7942 товарів.

### Як Claude виконує маппінг (технічні деталі)

Horoshop import preview працює всередині **`iframe[0]`** на сторінці `/edit/products/all`.
Інтерфейс побудований на **Vue 2 + Vuex**. Маппінг керується через Vuex action:

```javascript
store.dispatch('DataGrid/setSelectedColumnById', {columnId: N, selectedIndex: M})
```

де `columnId` — індекс колонки (0-based), `selectedIndex` — id поля з `availableGroups`.

#### Як отримати доступ до Vue store (шаблон для Claude):

```javascript
const iframe = document.querySelectorAll('iframe')[0];
const doc = iframe.contentDocument;
const divs = doc.querySelectorAll('div');
const roots = new Set();
for (const d of divs) { if (d.__vue__) roots.add(d.__vue__.$root); }
const root1 = Array.from(roots).find(r => !r.$options?.name);

function findComp(comp, name, depth=0) {
  if (depth>10) return null;
  if ((comp.$options?.name||comp.$options?._componentTag)===name) return comp;
  for (const c of (comp.$children||[])) { const f=findComp(c,name,depth+1); if(f) return f; }
  return null;
}

const theStart = findComp(root1, 'TheStart');
const dataTable = theStart.$children.find(c=>c.$options?.name==='DataTable');
const headerCols = dataTable.$children.filter(c=>c.$options?.name==='HeaderColumnSelect');
const store = headerCols[0].$store;
const ACTION = 'DataGrid/setSelectedColumnById';
```

#### Як отримати список всіх доступних полів (availableGroups):

```javascript
const ag = theStart.availableGroups;
// Повний список: id → назва поля
ag.map(g => `${g.id}: ${g.label} [${g.handler||''}]`)
```

#### Як побачити назви XML-колонок (перший рядок = заголовки):

```javascript
const firstRow = dataTable.$props.data[0];
firstRow.map((name, i) => `${i}: ${name}`)
```

#### Як перевірити поточний стан маппінгу:

```javascript
const idToLabel = {};
theStart.availableGroups.forEach(g => idToLabel[g.id] = g.label);
headerCols.map(c => ({
  colId: c.$props.colId,
  xmlField: firstRow[c.$props.colId],
  mappedTo: c.$props.selectId !== null ? idToLabel[c.$props.selectId] : 'Не імпортувати',
  error: c.$props.colError
}))
```

#### Як перевірити помилки (дублікати):

```javascript
JSON.stringify(theStart.$data.errors)
// Якщо `errors.used` не порожній — є дублікати, треба зробити deselect
```

### Повна таблиця маппінгу (horoshop.xml → Horoshop поле)

| colId | XML поле | selectId | Horoshop поле | Примітка |
|-------|----------|----------|---------------|----------|
| 0 | Родительский артикул | 1 | Родительский артикул | авто |
| 1 | Код вендора | null | Не імпортувати | не потрібен |
| 2 | Артикул | 0 | Артикул | авто |
| 3 | Раздел | 28 | Раздел | авто |
| **4** | **Название модификации(RU)** | **4** | **Название модификации (UA)** | **⚠️ КРИТИЧНО — назва товару!** |
| 5 | Цена | 5 | Цена | авто |
| 6 | Старая цена | 9 | Старая цена | авто |
| 7 | Валюта | 17 | Валюта | авто |
| 8 | Наличие | 10 | Наличие | авто |
| **9** | **Фото** | **13** | **Фото** | вручну |
| **10** | **Описание товара(RU)** | **34** | **Описание товара (UA)** | вручну |
| 11 | Доставка | null | Не імпортувати | |
| 12 | Страна производства | null | Не імпортувати | |
| 13 | Отображать | 11 | Отображать | авто |
| **14** | **Бренд** | **null** | **DESELECT** | **⚠️ дублікат — видалити!** |
| **15** | **name_ua** | **26** | **Название (UA)** | вручну |
| 16 | stock_quantity | null | Не імпортувати | Наличие вже є |
| 17 | article | null | Не імпортувати | дублікат Артикул |
| 18 | description_ua | null | Не імпортувати | те саме що col 10 |
| 19 | Тип вудилища | 72 | Тип вудилища (UA) | характ. |
| 20 | Тест | 79 | Тест (UA) | характ. |
| 21 | Кастинг-тест | 90 | Кастинг-тест (UA) | характ. |
| 22 | Довжина | 78 | Довжина (UA) | характ. |
| 23 | Матеріал бланка | 88 | Матеріал (UA) | характ. |
| 24 | Кількість секцій | null | Не імпортувати | немає поля |
| 25 | Транспортна довжина | null | Не імпортувати | немає поля |
| 26 | Тип пропускних кілець | null | Не імпортувати | немає поля |
| 27 | Тип рукояті | null | Не імпортувати | немає поля |
| 28 | Країна-виробник | null | Не імпортувати | немає поля |
| 29 | Вага | 84 | Вага (UA) | характ. |
| 30 | Стрій | 80 | Стрій (UA) | характ. |
| 31 | Лад | 91 | Лад (UA) | характ. |
| 32 | Розмір | 93 | Розмір (UA) | характ. |
| 33 | Транспортна довжина (см) | null | Не імпортувати | немає поля |
| 34 | Тип з'єднання секцій | null | Не імпортувати | немає поля |
| 35 | PE | 83 | PE (UA) | характ. |
| 36 | Діаметр | 81 | Діаметр (UA) | характ. |
| 37 | Розривне навантаження (lb) | null | Не імпортувати | немає окремого поля |
| 38 | Розривне навантаження | 82 | Розривне навантаження (UA) | характ. |
| 39 | Тип воблера | null | Не імпортувати | немає поля |
| 40 | Плавучість | 89 | Плавучість (UA) | характ. |
| 41 | Матеріал | null | Не імпортувати | id=88 вже зайнятий col 23 |
| 42 | Кількість гачків | null | Не імпортувати | немає поля |
| 43 | Тип котушки | null | Не імпортувати | немає поля |
| 44 | Передаточне число | null | Не імпортувати | немає поля |
| 45 | Матеріал корпусу | null | Не імпортувати | немає поля |
| 46 | Система гальма | null | Не імпортувати | немає поля |
| 47 | Підшипники | null | Не імпортувати | немає поля |
| 48 | Тип | 76 | Тип (UA) | характ. |
| 49 | Колір | null | Не імпортувати | немає поля хар-ки |
| 50 | Призначення | 86 | Призначення (UA) | характ. |
| 51 | Матеріал повідця | null | Не імпортувати | немає поля |
| 52 | Тип повідця | null | Не імпортувати | немає поля |
| 53 | Кількість в упаковці | 85 | Кількість в упаковці (UA) | характ. |
| **54** | **Бренд** | **30** | **Бренд** | вручну (після deselect col14) |
| 55 | Модель | null | Не імпортувати | немає поля |
| 56 | Використання | null | Не імпортувати | немає поля |
| 57 | Аромат | 87 | Аромат (UA) | характ. |
| 58 | Тип насадки | 73 | Тип насадки (UA) | характ. |
| 59-61 | Виробник, Клас, Покриття | null | Не імпортувати | немає полів |
| 62 | Об'єм | 92 | Об'єм (UA) | характ. |
| 63 | Підтип | 77 | Підтип (UA) | характ. |
| 64-77 | різні | null | Не імпортувати | немає полів |
| 78 | Тип атрактанту | 75 | Тип атрактанту (UA) | характ. |
| 79-86 | різні | null | Не імпортувати | немає полів |
| 87 | Тип суміші | 74 | Тип суміші (UA) | характ. |
| 88-96 | різні | null | Не імпортувати | немає полів |

### JS-скрипт для повного автоматичного маппінгу (для Claude)

Виконати у Chrome MCP через `javascript_tool` на tabId сторінки `/edit/products/all`:

```javascript
const iframe = document.querySelectorAll('iframe')[0];
const doc = iframe.contentDocument;
const divs = doc.querySelectorAll('div');
const roots = new Set();
for (const d of divs) { if (d.__vue__) roots.add(d.__vue__.$root); }
const root1 = Array.from(roots).find(r => !r.$options?.name);
function findComp(comp, name, depth=0) {
  if (depth>10) return null;
  if ((comp.$options?.name||comp.$options?._componentTag)===name) return comp;
  for (const c of (comp.$children||[])) { const f=findComp(c,name,depth+1); if(f) return f; }
  return null;
}
const theStart = findComp(root1, 'TheStart');
const dataTable = theStart.$children.find(c=>c.$options?.name==='DataTable');
const headerCols = dataTable.$children.filter(c=>c.$options?.name==='HeaderColumnSelect');
const store = headerCols[0].$store;
const ACTION = 'DataGrid/setSelectedColumnById';

const mappings = [
  // [colId, selectId]  — null = deselect (видалити маппінг)
  [4,  4],    // Название модификации(RU) → Название модификации (UA) *** КРИТИЧНО ***
  [9,  13],   // Фото → Фото
  [10, 34],   // Описание товара(RU) → Описание товара (UA)
  [14, null], // Бренд (дублікат) → DESELECT
  [15, 26],   // name_ua → Название (UA)
  [19, 72],   // Тип вудилища → Тип вудилища (UA)
  [20, 79],   // Тест → Тест (UA)
  [21, 90],   // Кастинг-тест → Кастинг-тест (UA)
  [22, 78],   // Довжина → Довжина (UA)
  [23, 88],   // Матеріал бланка → Матеріал (UA)
  [29, 84],   // Вага → Вага (UA)
  [30, 80],   // Стрій → Стрій (UA)
  [31, 91],   // Лад → Лад (UA)
  [32, 93],   // Розмір → Розмір (UA)
  [35, 83],   // PE → PE (UA)
  [36, 81],   // Діаметр → Діаметр (UA)
  [38, 82],   // Розривне навантаження → Розривне навантаження (UA)
  [40, 89],   // Плавучість → Плавучість (UA)
  [48, 76],   // Тип → Тип (UA)
  [50, 86],   // Призначення → Призначення (UA)
  [53, 85],   // Кількість в упаковці → Кількість в упаковці (UA)
  [54, 30],   // Бренд → Бренд (після deselect col14)
  [57, 87],   // Аромат → Аромат (UA)
  [58, 73],   // Тип насадки → Тип насадки (UA)
  [62, 92],   // Об'єм → Об'єм (UA)
  [63, 77],   // Підтип → Підтип (UA)
  [78, 75],   // Тип атрактанту → Тип атрактанту (UA)
  [87, 74],   // Тип суміші → Тип суміші (UA)
];

for (const [colId, selectedIndex] of mappings) {
  store.dispatch(ACTION, {columnId: colId, selectedIndex});
}

// Перевірити помилки після маппінгу
JSON.stringify(theStart.$data.errors)
// Очікуємо: {"used":{},"required":{},"miscMessages":{}}
```

---

## 4. Оновлення товарів (щоденна синхронізація)

```bash
cd D:\FISH\fish-sync

# 1. Отримати свіжі дані з УкрСклад
python src\sync.py

# 2. Перегенерувати фіди
python src\render_horoshop.py
python src\render_rozetka.py
python src\render_facebook.py

# 3. Зробити бекап
xcopy /E /I public\*.xml public\backup_%date:~6,4%%date:~3,2%%date:~0,2%\

# 4. Імпортувати в Horoshop (повторити Крок 4 + Розділ 3)
# При оновленні: "Існуючі товари → Оновити", "Нові → Імпортувати"
```

---

## 5. Структура магазину Horoshop

| Параметр | Значення |
|---|---|
| URL адмін | `https://vsedliarybalky.com.ua/edit/` |
| Логін | див. локальний `.env` |
| Пароль | див. локальний `.env` |
| Legacy admin | `https://vsedliarybalky.com.ua/adminLegacy/` |
| checkcode | yamete_kudasai |
| ID розділу Каталог | 97 |
| Шаблон "КАТАЛОГ: Товар" | 381 |
| Шаблон "КАТАЛОГ: Вудилища" | 451 |
| Шаблон "КАТАЛОГ: Волосінь та шнури" | 452 |
| Шаблон "КАТАЛОГ: Насадки та бойли" | 453 |
| Шаблон "КАТАЛОГ: Прикормка і пелетси" | 460 |

---

## 6. Структура XML-фіду (horoshop.xml)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<yml_catalog date="2026-04-25 14:00">
  <shop>
    <name>Все для рибалки</name>
    <categories>
      <category id="9">Спінінг</category>
    </categories>
    <offers>
      <offer id="240" available="true">
        <name>Спінінг KAIDA Exellence 2.4м (5-25г)</name>       ← col4 "Название модификации(RU)"
        <name_ua>Спінінг KAIDA Exellence 2.4м (5-25г)</name_ua> ← col15 "name_ua"
        <price>470.00</price>
        <currencyId>UAH</currencyId>
        <categoryId>9</categoryId>         ← Повинна існувати в Horoshop!
        <stock_quantity>0</stock_quantity>
        <article>240</article>
        <vendor>KAIDA</vendor>              ← Бренд через <vendor>, не через <param>
        <picture>https://...</picture>
        <description><![CDATA[<p>Опис...</p>]]></description>
        <description_ua><![CDATA[<p>Опис...</p>]]></description_ua>
        <param name="Тип вудилища">Спінінгові</param>
        <param name="Кастинг-тест">5-25 г</param>
        <param name="Довжина">2.4 м</param>
      </offer>
    </offers>
  </shop>
</yml_catalog>
```

**⚠️ Важливо:** `<categoryId>` матчиться з Horoshop за **назвою** категорії (не ID).

---

## 7. Типові помилки та їх виправлення

### "Невозможно обработать загруженный файл"
**Причина:** XML містить заборонені символи (\x00-\x08, \x0B, \x0C, \x0E-\x1F, \x7F)
**Рішення:** У `render_horoshop.py` є функція `_sanitize()` яка їх видаляє.

### "Категорія Спінінг не знайдена, або в категорії вказаний неправильний шаблон"
**Причина:** Категорія не існує в Horoshop АБО не має призначеного шаблону (handler)
**Рішення:** Виконати Крок 3 — масове створення категорій із шаблоном 381

### "не вказано назва товару" (7942 помилки)
**Причина:** Колонка `<name>` з XML відображається як "Название модификации(RU)" і **не маппується автоматично**
**Рішення:** Виконати JS-скрипт маппінгу (Розділ 3) — встановити `col4 → selectId=4`

### "Для стовпців обрано однакову характеристику: Бренд [КАТАЛОГ]"
**Причина:** XML має `<vendor>` (→ Бренд, col14) і `<param name="Бренд">` (→ Бренд, col54) — обидва маппуються на Бренд
**Рішення:** Зробити deselect col14 (`{columnId:14, selectedIndex:null}`), і замапити col54 → selectId=30

### Категорія створюється але не зберігається (save.php повертає 200, але порожньо)
**Причина:** `names[handler]=0` — не вказано шаблон. Horoshop мовчки ігнорує збереження без шаблону.
**Рішення:** Завжди передавати `names[handler]='381'` і використовувати `FormData` (не `URLSearchParams`)

### Помилки при імпорті (червоні рядки, ~108 помилок для деяких категорій)
**Причина:** Деякі категорії (наприклад "Зимові вудки") мають шаблон без характеристик
**Рішення:** У легасі-адміні призначити правильний шаблон для таких категорій

---

## 8. Як Claude взаємодіє з Horoshop (технічні деталі для Claude)

### Архітектура сторінки
- `/edit/products/all` — основна сторінка Vue 3
- Імпорт preview завантажується у **`iframe[0]`** (`adminLegacy/data.php?handler=17`)
- Iframe використовує **Vue 2** + Vuex store
- Chrome MCP `javascript_tool` може читати DOM iframe через `document.querySelectorAll('iframe')[0].contentDocument`

### Знаходження компонентів у Vue 2 (шаблон)
```javascript
// Знайти root Vue instance
const roots = new Set();
doc.querySelectorAll('div').forEach(d => { if (d.__vue__) roots.add(d.__vue__.$root); });
const root1 = Array.from(roots).find(r => !r.$options?.name); // головний root (не QNotifications)

// Рекурсивний пошук компонента за іменем
function findComp(comp, name, depth=0) {
  if (depth>10) return null;
  if ((comp.$options?.name||comp.$options?._componentTag)===name) return comp;
  for (const c of (comp.$children||[])) { const f=findComp(c,name,depth+1); if(f) return f; }
  return null;
}

// Ієрархія: root → ThePage → TheStart → DataTable → HeaderColumnSelect[] → ColumnAttachSelect
```

### Vuex actions для маппінгу
```javascript
// Встановити маппінг колонки
store.dispatch('DataGrid/setSelectedColumnById', {columnId: N, selectedIndex: M})
// Зняти маппінг (deselect)
store.dispatch('DataGrid/setSelectedColumnById', {columnId: N, selectedIndex: null})
```

### Корисні дані з Vue компонентів
```javascript
// Всі доступні поля Horoshop для маппінгу
theStart.availableGroups  // [{id, label, handler, value}, ...]

// Назви XML-колонок (перший рядок = заголовки)
dataTable.$props.data[0]  // ["Родительский артикул", "Код вендора", ...]

// Поточний стан маппінгу кожної колонки
headerCols.map(c => ({colId: c.$props.colId, selectId: c.$props.selectId, error: c.$props.colError}))

// Помилки (дублікати, відсутні обов'язкові поля)
theStart.$data.errors  // {used:{}, required:{}, miscMessages:{}}

// Запустити імпорт (після натискання "Імпортувати" і налаштування діалогу)
doc.querySelector('button') // знайти кнопку "Почати імпорт" і натиснути .click()
```

---

## 9. AI-генерація описів (OpenAI GPT-4o-mini)

```bash
# Одиночний запуск (для перевірки)
python src\ai_generator.py --limit 5

# Масовий запуск (5 паралельних воркерів)
for /L %i in (0,1,4) do start python src\ai_generator.py --worker %i --workers 5

# Виключити family=other (економить ~30% бюджету)
python src\ai_generator.py --worker 0 --workers 5 --exclude-family other
```

Ключ зберігається в `D:\FISH\fish-sync\.env`:
```
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o-mini
```

**Вартість:** ~$2 для всіх 8 311 батьківських моделей, ~$1.4 без family=other

---

## 10. Файли проекту

```
D:\FISH\fish-sync\
├── src\
│   ├── sync.py              # УкрСклад → products.json
│   ├── meta_store.py        # Синхронізація variants/models до SQLite
│   ├── catalog_rules.py     # Regex-парсинг характеристик з назв
│   ├── ai_generator.py      # GPT-4o-mini генерація описів
│   ├── feed_content.py      # Спільні функції для фідів
│   ├── render_horoshop.py   # → public/horoshop.xml
│   ├── generate_import_xls.py # → public/horoshop_import.xlsx
│   ├── generate_import_yml.py # → public/horoshop_import.yml
│   ├── generate_import_csv.py # → public/horoshop_import_legacy.csv
│   ├── render_rozetka.py    # → public/rozetka.xml
│   └── render_facebook.py  # → public/facebook.xml
├── data\
│   ├── products.json        # Сирі дані з УкрСклад
│   ├── meta_store.sqlite    # AI-описи, характеристики, картинки
│   └── categories_list.txt  # Список категорій (id|parent|name|count)
├── public\
│   ├── horoshop.xml         # Horoshop XML/YML, 7942 товари
│   ├── horoshop_import.yml  # YML для Horoshop, 7942 товари
│   ├── horoshop_import.xlsx # Excel для Horoshop, 7942 товари
│   ├── horoshop_import_legacy.csv # CSV для legacy preview, 7942 товари
│   ├── rozetka.xml          # Rozetka feed
│   ├── facebook.xml         # Facebook/Instagram feed
│   └── backup_20260425_1424\
├── docs\
│   └── horoshop_import_guide.md  # Цей файл
└── .env                     # API ключі
```
### Важливо: одне джерело правди

Зараз правильний Horoshop-контур побудовано навколо `src/horoshop_catalog.py`.
Саме він формує:

- назву товару
- бренд
- опис
- характеристики
- наявність
- категорію

`render_horoshop.py`, `generate_import_xls.py`, `generate_import_yml.py` і `horoshop_sync.py`
використовують цей канонічний шар, а не власну окрему логіку.

Тому якщо треба змінити якість даних для Horoshop, правки треба робити в:

- `src/horoshop_catalog.py`
- `src/catalog_rules.py`
- `data/meta_store.sqlite` / джерелі `products.json`

а не в кількох різних рендерах окремо.

### Quality gate

Після кожного прогону пайплайн формує два службові звіти:

- `data/horoshop_audit_report.json` — агреговані метрики якості
- `data/horoshop_quarantine_report.json` — товари для ручного перегляду

У quarantine зараз потрапляють:

- товари, явно виключені через `data/horoshop_overrides.json`
- підозрілі назви
- товари з дуже малою кількістю характеристик
- товари без бренду

Точкові ручні виправлення треба вносити в:

- `data/horoshop_overrides.json`

а не в generated-файли в `public/`.
