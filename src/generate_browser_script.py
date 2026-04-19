"""
Генерує JS-скрипт для вставки в консоль браузера.
Скрипт масово створює/оновлює товари через save.php (браузерна сесія).

Запуск:
  py src/generate_browser_script.py
  → створює public/horoshop_browser_sync.js

Далі:
  1. Відкрий http://shop645299.horoshop.ua/adminLegacy/extensions/dashboard.php
  2. Натисни F12 → Console
  3. Вставте вміст файлу horoshop_browser_sync.js і натисни Enter
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT       = Path(__file__).parent.parent
PRODUCTS   = ROOT / "data" / "products.json"
OUT_JS     = ROOT / "public" / "horoshop_browser_sync.js"
HANDLER    = "460"
PARENT     = "1082"
CHECKCODE  = "yamete_kudasai"


def load_products() -> list[dict]:
    raw = json.loads(PRODUCTS.read_text(encoding="utf-8"))
    result = []
    for p in raw.get("products", []):
        kod = (p.get("kod") or "").strip()
        if not kod or kod in ("Код",):
            continue
        name = (p.get("name") or kod).strip()
        price = p.get("cena_r") or p.get("cena_o") or 0
        qty   = int(p.get("stock") or 0)
        brand = (p.get("proizv") or "").strip()
        descr = (p.get("descr_big") or "").strip()
        result.append({
            "a": kod,
            "t": name,
            "p": float(price),
            "q": qty,
            "b": brand,
            "d": descr,
        })
    return result


def generate_js(products: list[dict]) -> str:
    prods_json = json.dumps(products, ensure_ascii=False)
    return f"""
// ============================================================
// Horoshop browser sync — {len(products)} товарів
// Вставте в консоль браузера на сторінці адмінки Horoshop
// ============================================================
(async () => {{
  const HANDLER   = "{HANDLER}";
  const PARENT    = "{PARENT}";
  const CHECKCODE = "{CHECKCODE}";
  const products  = {prods_json};

  // Отримуємо базову форму для нового товару
  async function getBaseForm() {{
    const r = await fetch(`/adminLegacy/edit.php?handler=${{HANDLER}}&parent=${{PARENT}}&checkcode=${{CHECKCODE}}`, {{credentials:'include'}});
    const html = await r.text();
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const form = doc.querySelector('form[name=editDoc]') || doc.querySelector('form');
    if (!form) return null;
    const fd = new FormData(form);
    return fd;
  }}

  // Пошук ID товару за артикулом через API
  async function findProductId(article) {{
    const r = await fetch(`/adminLegacy/data.php?handler=${{HANDLER}}&parent=${{PARENT}}&limit=200`, {{credentials:'include'}});
    const j = await r.json();
    const item = (j.data || []).find(p => p.article === article || (p.modifications && p.modifications[0] && p.modifications[0].article === article));
    return item ? item.id : null;
  }}

  // Зберегти один товар (create або update)
  async function saveProduct(fd, prod, existingId) {{
    fd.set('handler',   HANDLER);
    fd.set('checkcode', CHECKCODE);
    if (existingId) fd.set('id', String(existingId));
    else            fd.delete('id');

    fd.set('parent_common[parent]',               PARENT);
    fd.set('parent_common[i18n][3][title]',        prod.t);
    fd.set('parent_common[brand]',                 prod.b || '');
    fd.set('parent_common[i18n][3][description]',  prod.d ? '<p>' + prod.d + '</p>' : '');
    fd.set('modifications[0][article]',             prod.a);
    fd.set('modifications[0][i18n][3][mod_title]', prod.t);
    fd.set('modifications[0][price]',              String(prod.p || 0));
    fd.set('modifications[0][currency]',           '1');
    fd.set('modifications[0][presence]',           prod.q > 0 ? '1' : '2');
    fd.set('modifications[0][display_in_showcase]','1');
    fd.set('modifications[0][quantity]',           String(prod.q || 0));

    const resp = await fetch('/adminLegacy/save.php', {{
      method: 'POST', credentials: 'include',
      headers: {{'X-Requested-With': 'XMLHttpRequest'}},
      body: fd
    }});
    const text = await resp.text();
    return resp.status === 200 && text.includes('збережено');
  }}

  console.log(`Завантаження форми...`);
  const baseFormData = await getBaseForm();
  if (!baseFormData) {{ console.error('Не вдалось отримати форму!'); return; }}

  console.log(`Завантаження списку товарів...`);
  const listResp = await fetch(`/adminLegacy/data.php?handler=${{HANDLER}}&parent=${{PARENT}}&limit=500`, {{credentials:'include'}});
  const listJson = await listResp.json();
  const existingMap = {{}};
  for (const item of (listJson.data || [])) {{
    const art = item.article || (item.modifications && item.modifications[0] && item.modifications[0].article);
    if (art) existingMap[art] = item.id;
  }}
  console.log(`Існуючих товарів: ${{Object.keys(existingMap).length}}`);

  let created = 0, updated = 0, failed = 0;
  for (let i = 0; i < products.length; i++) {{
    const prod = products[i];
    const existingId = existingMap[prod.a] || null;
    const action = existingId ? 'UPD' : 'NEW';

    // Копіюємо FormData для кожного товару
    const fd = new FormData();
    for (const [k, v] of baseFormData.entries()) fd.set(k, v);

    const ok = await saveProduct(fd, prod, existingId);
    if (ok) {{ if (existingId) updated++; else created++; }}
    else failed++;

    console.log(`[${{i+1}}/${{products.length}}] ${{action}} ${{prod.a}} — ${{ok ? 'OK' : 'FAIL'}}`);
    await new Promise(r => setTimeout(r, 300));
  }}

  console.log(`\\n=== Готово ===`);
  console.log(`Створено: ${{created}}, Оновлено: ${{updated}}, Помилок: ${{failed}}`);
}})();
""".strip()


if __name__ == "__main__":
    products = load_products()
    print(f"Товарів для синхронізації: {len(products)}")
    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    js = generate_js(products)
    OUT_JS.write_text(js, encoding="utf-8")
    print(f"JS-скрипт збережено: {OUT_JS}")
    print()
    print("Далі:")
    print("  1. Відкрий http://shop645299.horoshop.ua/adminLegacy/extensions/dashboard.php")
    print("  2. F12 → Console")
    print("  3. Вставте вміст файлу та натисніть Enter")
