# Модульні шаблони описів для фіду

## Що реалізовано

- Додано пакет `src/description_templates/`, де **кожна категорія/сімейство** має окремий файл шаблону:
  - `spinning.py`
  - `float_rod.py`
  - `line.py`
  - `fluorocarbon.py`
  - `shock_leader.py`
  - `ready_leader.py`
  - `grain_bait.py`
  - `nod.py`
  - `bite_indicator.py`
  - `rod_rest_accessory.py`
  - `other.py`
- Реєстр шаблонів: `src/description_templates/__init__.py`
- Базовий контекст і збір HTML: `src/description_templates/base.py`
- Підключення в рендерери через `src/feed_content.py`

## Як працює fallback

1. Якщо в `meta_store.models.description_html` є текст — використовуємо його.
2. Якщо опис порожній — беремо шаблон з файлу категорії.
3. Якщо категорія невідома — `other.py`.

## Додатково для групування

- Для Facebook додається `<g:item_group_id>` (через `parent_key`).
- Назви варіантів у фідах формуються з відмінною ознакою (довжина/тест/діаметр тощо), щоб варіанти однієї моделі не дублювалися текстово.

## Smoke-тест (2 товари з кожної категорії)

```bash
D:\FISH\fish-sync\.venv\Scripts\python.exe D:\FISH\fish-sync\src\smoke_feed_sample.py
```

Результат:
- формуються тестові фіди у `D:\FISH\fish-sync\tmp\feed_smoke\`
- перевіряється кількість елементів у кожному фіді
- виводиться зведення по категоріях та групах
