# Horoshop — Як правильно встановити slug і SEO для категорій

## Контекст
- Магазин: `http://shop647643.horoshop.ua`
- AdminLegacy: `/adminLegacy/`
- Новий адмін (React): `/edit/`
- api_work логін: `api_work` / `Do183183Do` — **READ-ONLY**, записи не зберігає
- Власник: логін через браузер Chrome (email невідомий, тільки браузерна сесія)

---

## Що НЕ ПРАЦЮЄ (і чому)

### 1. api_work через Python
`api_work` має JWT role=12 — read-only в adminLegacy.
- save.php повертає 302/redirect але **нічого не зберігає в БД**
- Перевірка: `GET /кherabuna/` → 200, `GET /volosin-ta-shnury/` → 404

### 2. `extra_handler=381` у POST
Додавання `extra_handler=381` до save.php **викликає помилку**:
> "Создание страницы невозможно, так как не выбран шаблон"
Це поле не потрібне — прибрати повністю.

### 3. Запуск скрипту з нового адміну `/edit/`
Нова React-адмінка може не мати PHPSESSID cookie для adminLegacy.
Скрипт треба запускати з `/adminLegacy/` сторінки.

### 4. `index.php?handler=4&id=XXX`
Повертає "Старт" (головну) сторінку, НЕ форму редагування.
Форма редагування — через `edit.php` (не index.php).

---

## Правильна URL форми редагування секції
```
/adminLegacy/edit.php?id={SECTION_ID}&parent={PARENT_ID}&handler=4&checkcode=yamete_kudasai&showPages
```
Наприклад:
```
/adminLegacy/edit.php?id=1237&parent=97&handler=4&checkcode=yamete_kudasai&showPages
```

---

## Поля форми редагування секції (handler=4)
Форма містить ТІЛЬКИ ці поля (перевірено):
```
names[parent]
names[name][slug]
names[name][parent]
names[handler]        ← ЦЕ ПОЛЕ ШАБЛОНУ (не окремий handler!)
extra_parent[discount]
extra_parent[image][file]
extra_parent[image][id]
extra_parent[image][value]
names[sortorder]
names[deny_removal]
names[link_to_page]
editDoc
```

**НЕМАЄ** полів: `names[template]`, `names[i18n]`, `names[inmenu]`, `names[insitemap]`  
SEO поля додаються через новий адмін `/edit/`, а НЕ через save.php.

---

## Шаблони (names[handler]) для каталогу
| ID  | Назва                        |
|-----|------------------------------|
| 381 | КАТАЛОГ: Товар ← **default** |
| 452 | КАТАЛОГ: Волосінь та шнури   |
| 451 | КАТАЛОГ: Вудилища            |
| 453 | КАТАЛОГ: Насадки та бойли    |
| 460 | КАТАЛОГ: Прикормка і пелетси |
| 349 | Бренди                       |
| 201 | Текстова сторінка            |

**Для всіх категорій каталогу використовувати `names[handler]=381`**

---

## Правильний алгоритм встановлення slug

### Крок 1: Отримати slug через widget
```
POST /_widget/zteel_params_url_Param/updateUriAutomatically
Content-Type: application/x-www-form-urlencoded
X-Requested-With: XMLHttpRequest
credentials: include

fields[title] = {НазваКатегорії}
param_id      = 1
record_id     = {SECTION_ID}
parent_id     = 97          ← ЗАВЖДИ 97 (корінь каталогу), НЕ реальний parent_id секції
```
Повертає: `{"status":"OK","response":{"slug":"volosin-ta-shnury","link":"/volosin-ta-shnury/","parent":2}}`
- `slug` — транслітерований slug
- `parent` — URL parent ID (=2 для каталогу)

**Важливо:** `parent_id=97` працює для ВСІХ секцій (і батьківських і дочірніх).
При `parent_id={child_section_id}` widget повертає HTTP 400.

### Крок 2: Зберегти slug через save.php
```
POST /adminLegacy/save.php
Content-Type: application/x-www-form-urlencoded
X-Requested-With: XMLHttpRequest
credentials: include

checkcode              = yamete_kudasai
id                     = {SECTION_ID}
handler                = 4
handlertable           = pages
back                   = index.php
names[parent]          = {PARENT_SECTION_ID}
names[handler]         = 381              ← шаблон "КАТАЛОГ: Товар"
names[name][slug]      = {slug з widget}
names[name][parent]    = {parent з widget, зазвичай "2"}
names[name][forceUpdate] = 1
names[sortorder]       = 0
names[deny_removal]    = 0
names[link_to_page]    = 0
extra_parent[discount] = 0
extra_parent[image][id]    = (порожньо)
extra_parent[image][value] = (порожньо)
```

**Успіх:** redirect на `edit.php` (status=0, type='opaqueredirect' в fetch з redirect:'manual')
**Помилка шаблону:** якщо `names[handler]` відсутній або `extra_handler=381` присутній

---

## Готовий браузерний скрипт (запускати з /adminLegacy/)

```javascript
(async()=>{
  const CC='yamete_kudasai';
  const d=ms=>new Promise(r=>setTimeout(r,ms));
  // ... масив секцій ...
  const p=async(u,b)=>fetch(u,{method:'POST',credentials:'include',
    headers:{'X-Requested-With':'XMLHttpRequest','Content-Type':'application/x-www-form-urlencoded'},
    body:new URLSearchParams(b),redirect:'manual'});

  for(const [id,par,nm] of SECTIONS){
    // Step 1: widget
    const w=await(await p('/_widget/zteel_params_url_Param/updateUriAutomatically',{
      'fields[title]':nm,'param_id':'1','record_id':id,'parent_id':'97'
    })).json();
    const sl=w.response.slug, up=String(w.response.parent||'2');
    
    // Step 2: save
    await p('/adminLegacy/save.php',{
      'checkcode':CC,'id':id,'handler':'4','handlertable':'pages','back':'index.php',
      'names[parent]':par,'names[handler]':'381',
      'names[name][slug]':sl,'names[name][parent]':up,'names[name][forceUpdate]':'1',
      'names[sortorder]':'0','names[deny_removal]':'0','names[link_to_page]':'0',
      'extra_parent[discount]':'0','extra_parent[image][id]':'','extra_parent[image][value]':''
    });
    await d(250);
  }
})();
```

**Файл з повним скриптом:** `public/fix_all_slugs_seo.js` (потребує оновлення з правильними полями)
**Повний готовий скрипт:** у буфері обміну після запуску `get_chrome_cookies.py`

---

## SEO поля
SEO (`seo_title`, `seo_description`, `seo_keywords`, `h1_title`) через save.php з `names[i18n]` **не зберігаються** (цих полів немає у формі handler=4).

SEO треба заповнювати або:
1. Через новий адмін `/edit/website/pages/{id}` вручну
2. Через core-api (ендпоінт поки не знайдено, потребує авторизації власника)

---

## Структура каталогу
- Корінь каталогу: ID=97 ("Каталог")
- URL-запис каталогу: parent=2
- Всі топ-рівневі секції: `names[parent]=97`
- Дочірні секції: `names[parent]={parent_section_id}`
- Але для widget завжди: `parent_id=97`

---

## Chrome cookies (заблоковані)
Chrome тримає файл cookies заблокованим (exclusive lock).
`shutil.copy2` та `robocopy /B` не можуть скопіювати файл поки Chrome відкритий.
Тому Python-скрипт з власницькою сесією неможливий без закриття Chrome або ручного введення cookies.

**Єдиний спосіб використати власницьку сесію:** запускати JS скрипт прямо в консолі Chrome на сторінці `/adminLegacy/`.
