from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import requests
import urllib3


urllib3.disable_warnings()

ROOT = Path(r"D:\FISH\fish-sync")
ENV_FILE = ROOT / ".env"
REPORT = ROOT / "data" / "horoshop_content_pages_fill_report.json"


PAGES: dict[str, dict[str, str]] = {
    "927": {
        "parent": "1",
        "slug": "pro-nas",
        "title": "Про нас",
        "h1": "Про магазин «Все для рибалки»",
        "seo_title": "Про нас — Все для рибалки",
        "seo_description": "Все для рибалки — магазин рибальських снастей у Хмельницькому та онлайн з доставкою по Україні.",
        "seo_keywords": "все для рибалки, рибальський магазин, снасті, Хмельницький",
        "text": """
<h1>Про магазин «Все для рибалки»</h1>
<p><strong>Все для рибалки</strong> — магазин рибальських товарів у Хмельницькому та онлайн-каталог для рибалок по всій Україні.</p>
<p>Ми підбираємо снасті для коропової, фідерної, спінінгової, поплавкової, зимової ловлі та туризму. У каталозі є вудилища, котушки, волосінь і шнури, гачки, монтажі, годівниці, грузила, прикормка, пелетси, насадки, PVA-матеріали, підсаки, крісла, органайзери й аксесуари.</p>
<p>Якщо ви не впевнені, що саме підійде під вашу водойму, сезон або стиль ловлі, напишіть чи зателефонуйте нам — допоможемо підібрати комплект без зайвого.</p>
<ul>
  <li>Фізичний магазин: м. Хмельницький, вул. Народної Волі, 1.</li>
  <li>Телефон: <a href="tel:+380678957371">067 895-73-71</a>.</li>
  <li>Доставка: Нова пошта, самовивіз із магазину, Укрпошта для компактних негабаритних посилок за погодженням.</li>
</ul>
<h2>Юридична інформація</h2>
<p>Продавець: <strong>ФОП Гулівата Марина Андріївна</strong><br>
РНОКПП: 3285915727<br>
Адреса: вул. Народної Волі, 1, м. Хмельницький, Україна<br>
Телефон: <a href="tel:+380678957371">067 895-73-71</a><br>
Email: <a href="mailto:vsedliarybalky@gmail.com">vsedliarybalky@gmail.com</a></p>
""",
    },
    "928": {
        "parent": "1",
        "slug": "oplata-i-dostavka",
        "title": "Оплата і доставка",
        "h1": "Оплата і доставка",
        "seo_title": "Оплата і доставка — Все для рибалки",
        "seo_description": "Умови оплати та доставки рибальських товарів: самовивіз у Хмельницькому, Нова пошта, Укрпошта для негабаритних посилок за погодженням.",
        "seo_keywords": "оплата, доставка, нова пошта, укрпошта, рибальські товари",
        "text": """
<h1>Оплата і доставка</h1>
<h2>Способи доставки</h2>
<ul>
  <li><strong>Самовивіз</strong> — м. Хмельницький, вул. Народної Волі, 1.</li>
  <li><strong>Нова пошта</strong> — у відділення, поштомат або кур'єром за тарифами перевізника.</li>
  <li><strong>Укрпошта</strong> — тільки для компактних негабаритних посилок за попереднім погодженням з менеджером.</li>
</ul>
<h2>Способи оплати</h2>
<ul>
  <li>Онлайн-оплата банківською карткою через LiqPay (Visa, Mastercard).</li>
  <li>Оплата при отриманні замовлення.</li>
  <li>Оплата у фізичному магазині при самовивозі.</li>
  <li>Переказ за реквізитами після підтвердження замовлення менеджером.</li>
</ul>
<p>Після оформлення замовлення ми перевіряємо наявність товарів, погоджуємо деталі та передаємо замовлення в обробку. Зазвичай обробка замовлення займає 3-4 дні, оскільки частину позицій потрібно перевірити, зібрати та правильно запакувати. Вартість доставки залежить від тарифів перевізника, ваги та габаритів посилки.</p>
<p>Для великих або габаритних замовлень Укрпошту краще не обирати. Якщо потрібне вантажне відправлення, менеджер окремо погодить доступний спосіб доставки, бо вантажне відділення Укрпошти у місті працює не всюди зручно.</p>
""",
    },
    "573": {
        "parent": "1",
        "slug": "obmin-ta-povernennya",
        "title": "Обмін та повернення",
        "h1": "Обмін та повернення",
        "seo_title": "Обмін та повернення — Все для рибалки",
        "seo_description": "Умови обміну та повернення товарів у магазині Все для рибалки згідно із законодавством України.",
        "seo_keywords": "обмін, повернення, гарантія, рибальські товари",
        "text": """
<h1>Обмін та повернення</h1>
<p>Обмін або повернення товару здійснюється відповідно до чинного законодавства України.</p>
<h2>Коли можливе повернення</h2>
<ul>
  <li>Товар не був у використанні та збережив товарний вигляд.</li>
  <li>Збережені упаковка, ярлики, комплектація та розрахунковий документ.</li>
  <li>З моменту отримання товару не минуло 14 днів, якщо інше не передбачено законом.</li>
</ul>
<h2>Як оформити повернення</h2>
<p>Зв'яжіться з нами за телефоном <a href="tel:+380678957371">067 895-73-71</a>, повідомте номер замовлення та причину звернення. Менеджер підкаже подальші дії.</p>
<p>Якщо товар має виробничий дефект, ми допоможемо узгодити обмін, повернення або гарантійне звернення.</p>
""",
    },
    "686": {
        "parent": "1",
        "slug": "kontaktna-informatsiya",
        "title": "Контактна інформація",
        "h1": "Контактна інформація",
        "seo_title": "Контактна інформація — Все для рибалки",
        "seo_description": "Контакти магазину Все для рибалки: телефон, адреса у Хмельницькому, графік роботи та консультація щодо рибальських снастей.",
        "seo_keywords": "контакти, все для рибалки, Хмельницький, телефон",
        "text": """
<h1>Контактна інформація</h1>
<p><strong>Магазин «Все для рибалки»</strong></p>
<ul>
  <li>Адреса: м. Хмельницький, вул. Народної Волі, 1.</li>
  <li>Телефон: <a href="tel:+380678957371">067 895-73-71</a>.</li>
  <li>Графік роботи: понеділок-субота 9:00-18:00, неділя — вихідний.</li>
</ul>
<p>Пишіть або телефонуйте, якщо потрібна консультація щодо підбору вудилища, котушки, монтажу, прикормки, насадки чи іншого спорядження.</p>
""",
    },
    "1052": {
        "parent": "1",
        "slug": "privacypolicy",
        "title": "Публічна оферта",
        "h1": "Публічна оферта та політика конфіденційності",
        "seo_title": "Публічна оферта та угода користувача — Все для рибалки",
        "seo_description": "Публічна оферта ФОП Гулівата Марина Андріївна (РНОКПП 3285915727): умови купівлі, оплати, доставки, повернення та обробки персональних даних.",
        "seo_keywords": "угода користувача, політика конфіденційності, персональні дані, публічна оферта",
        "text": """
<h1>Публічна оферта та політика конфіденційності</h1>
<p>Цей документ є публічною офертою відповідно до ст. 633, 641 Цивільного кодексу України. Оформлення замовлення на сайті vsedliarybalky.com.ua означає повне прийняття покупцем умов цієї оферти.</p>

<h2>1. Продавець</h2>
<p><strong>ФОП Гулівата Марина Андріївна</strong><br>
РНОКПП: 3285915727<br>
Адреса: вул. Народної Волі, 1, м. Хмельницький, 29000, Україна<br>
Телефон: <a href="tel:+380678957371">067 895-73-71</a><br>
Email: <a href="mailto:vsedliarybalky@gmail.com">vsedliarybalky@gmail.com</a><br>
Сайт: vsedliarybalky.com.ua</p>

<h2>2. Предмет оферти</h2>
<p>Продавець зобов'язується передати у власність покупця товари для риболовлі та туризму (вудилища, котушки, волосінь, прикормку, аксесуари та інше), а покупець зобов'язується прийняти та оплатити товар відповідно до умов цієї оферти.</p>

<h2>3. Оформлення замовлення</h2>
<p>Замовлення оформлюється через сайт, телефон або месенджер. Після отримання замовлення менеджер зв'язується з покупцем для підтвердження наявності товару, ціни, способу оплати та доставки. Договір купівлі-продажу вважається укладеним з моменту підтвердження замовлення менеджером та отримання оплати або домовленості про спосіб оплати.</p>

<h2>4. Ціни та наявність</h2>
<p>Ціни вказані в гривнях (UAH). Продавець прагне підтримувати актуальність цін та наявності. Якщо під час підтвердження замовлення ціна або наявність змінились, покупцю пропонується актуальний варіант, заміна або скасування позиції.</p>

<h2>5. Способи оплати</h2>
<ul>
  <li>Онлайн-оплата банківською карткою через LiqPay (Visa, Mastercard).</li>
  <li>Безготівковий переказ за реквізитами після підтвердження замовлення.</li>
  <li>Готівкою при самовивозі або при отриманні замовлення.</li>
</ul>

<h2>6. Доставка</h2>
<ul>
  <li><strong>Самовивіз:</strong> м. Хмельницький, вул. Народної Волі, 1 (пн-сб 9:00-18:00).</li>
  <li><strong>Нова пошта:</strong> у відділення, поштомат або кур'єром за тарифами перевізника.</li>
  <li><strong>Укрпошта:</strong> для компактних негабаритних посилок за попереднім погодженням.</li>
</ul>
<p>Вартість і строки доставки визначаються тарифами обраного перевізника. Ризик випадкової загибелі або пошкодження товару переходить до покупця з моменту передачі товару перевізнику.</p>

<h2>7. Обмін та повернення</h2>
<p>Повернення і обмін товарів належної якості здійснюється відповідно до Закону України «Про захист прав споживачів» протягом 14 днів з дня отримання товару (не рахуючи дня купівлі) за умови збереження товарного вигляду, упаковки, комплектації та розрахункового документа. Товар, що був у використанні, поверненню не підлягає. При виявленні виробничого дефекту покупець має право на безоплатний ремонт, заміну або повернення коштів.</p>

<h2>8. Персональні дані та конфіденційність</h2>
<p>Покупець надає згоду на обробку персональних даних (ім'я, телефон, адреса, email) для цілей виконання замовлення, доставки, зв'язку, гарантійного обслуговування та захисту прав споживача. Персональні дані не передаються третім особам, крім випадків, необхідних для виконання замовлення (служби доставки, платіжні сервіси), або передбачених чинним законодавством. Для припинення обробки даних або їх видалення звертайтеся за контактами продавця.</p>

<h2>9. Cookies та аналітика</h2>
<p>Сайт використовує cookies для коректної роботи кошика, авторизації, аналітики (Google Analytics) та покращення зручності. Продовжуючи користуватися сайтом, покупець погоджується з використанням cookies.</p>

<h2>10. Вирішення спорів</h2>
<p>Усі спори вирішуються шляхом переговорів. У разі неможливості досягнення домовленості спір передається до суду за місцем знаходження продавця (м. Хмельницький) відповідно до чинного законодавства України.</p>

<h2>11. Контакти</h2>
<p>З питань замовлень, повернень або персональних даних:<br>
Телефон: <a href="tel:+380678957371">067 895-73-71</a><br>
Email: <a href="mailto:vsedliarybalky@gmail.com">vsedliarybalky@gmail.com</a><br>
Адреса: вул. Народної Волі, 1, м. Хмельницький</p>
""",
    },
    "1053": {
        "parent": "1",
        "slug": "store-reviews",
        "title": "Відгуки про магазин",
        "h1": "Відгуки про магазин",
        "seo_title": "Відгуки про магазин — Все для рибалки",
        "seo_description": "Відгуки та приклади зворотного зв'язку про магазин Все для рибалки, консультації, підбір снастей і доставку.",
        "seo_keywords": "відгуки, все для рибалки, рибальський магазин, консультація",
        "text": """
<h1>Відгуки про магазин</h1>
<p>Ми збираємо реальні відгуки покупців після запуску оновленого сайту. Нижче — демонстраційний блок для погодження вигляду сторінки з клієнтом; перед публічним запуском його потрібно замінити на справжні відгуки покупців.</p>
<div class="demo-reviews">
  <blockquote><p>Підібрали фідерний комплект без нав'язування зайвого. Окремо пояснили по годівницях і шнуру, за це дякую.</p><footer>Приклад відгуку, м. Хмельницький</footer></blockquote>
  <blockquote><p>Замовлення швидко підтвердили, по наявності все перевірили. Зручно, що можна забрати в магазині.</p><footer>Приклад відгуку, самовивіз</footer></blockquote>
  <blockquote><p>Брав прикормку і насадки на коропа. Допомогли з ароматами під водойму, спрацювало добре.</p><footer>Приклад відгуку, коропова ловля</footer></blockquote>
  <blockquote><p>Потрібна була консультація по спінінгу для невеликої річки. Порадили адекватний варіант по бюджету.</p><footer>Приклад відгуку, спінінг</footer></blockquote>
</div>
<p>Якщо ви вже купували у нас, будемо вдячні за чесний відгук після замовлення — це допомагає іншим рибалкам швидше обрати потрібні снасті.</p>
""",
    },
}


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_FILE.exists():
        for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


class FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.payload: dict[str, Any] = {}
        self.current_textarea: str | None = None
        self.textarea_chunks: list[str] = []
        self.current_select: str | None = None
        self.current_select_value: str | None = None
        self.first_select_value: str | None = None

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {key: value or "" for key, value in attrs_list}
        name = attrs.get("name")
        if tag == "input" and name:
            input_type = attrs.get("type", "text").lower()
            if input_type in {"submit", "button", "file"}:
                return
            if input_type in {"checkbox", "radio"} and "checked" not in attrs:
                return
            self.payload[name] = attrs.get("value", "")
        elif tag == "textarea" and name:
            self.current_textarea = name
            self.textarea_chunks = []
        elif tag == "select" and name:
            self.current_select = name
            self.current_select_value = None
            self.first_select_value = None
        elif tag == "option" and self.current_select:
            value = attrs.get("value", "")
            if self.first_select_value is None:
                self.first_select_value = value
            if "selected" in attrs:
                self.current_select_value = value

    def handle_data(self, data: str) -> None:
        if self.current_textarea:
            self.textarea_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "textarea" and self.current_textarea:
            self.payload[self.current_textarea] = "".join(self.textarea_chunks)
            self.current_textarea = None
            self.textarea_chunks = []
        elif tag == "select" and self.current_select:
            self.payload[self.current_select] = self.current_select_value or self.first_select_value or ""
            self.current_select = None
            self.current_select_value = None
            self.first_select_value = None


def parse_form_payload(form_html: str) -> dict[str, Any]:
    parser = FormParser()
    parser.feed(form_html)
    return parser.payload


def page_slug_parent(session: requests.Session, base_url: str, page_id: str, slug: str) -> tuple[str, str]:
    response = session.post(
        f"{base_url}/_widget/zteel_params_url_Param/updateUriAutomatically",
        data={
            "fields[title]": slug,
            "param_id": "1",
            "record_id": page_id,
            "parent_id": "1",
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
        timeout=60,
        verify=False,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("status") == "OK":
        payload = data.get("response") or {}
        return str(payload.get("slug") or slug), str(payload.get("parent") or "1")
    return slug, "1"


def update_page(session: requests.Session, base_url: str, page_id: str, page: dict[str, str]) -> dict[str, str]:
    edit_url = f"{base_url}/adminLegacy/edit.php?id={page_id}&parent={page['parent']}&handler=4&checkcode=yamete_kudasai&showPages"
    response = session.get(edit_url, timeout=60, verify=False)
    response.raise_for_status()
    payload = parse_form_payload(response.text)

    slug, url_parent = page_slug_parent(session, base_url, page_id, page["slug"])
    payload.update(
        {
            "checkcode": "yamete_kudasai",
            "id": page_id,
            "handler": "4",
            "handlertable": "pages",
            "back": "index.php",
            "names[parent]": page["parent"],
            "names[name][slug]": slug,
            "names[name][parent]": url_parent,
            "names[name][forceUpdate]": "1",
            "names[i18n][3][title]": page["title"],
            "names[i18n][3][seo_title]": page["seo_title"],
            "names[i18n][3][seo_description]": page["seo_description"],
            "names[i18n][3][seo_keywords]": page["seo_keywords"],
            "names[i18n][3][h1_title]": page["h1"],
            "extra[i18n][3][title]": page["h1"],
            "extra[i18n][3][text]": page["text"].strip(),
            "names[inmenu]": "1",
            "names[insitemap]": "1",
            "names[noindex]": "0",
            "names[nofollow]": "0",
        }
    )
    save = session.post(
        f"{base_url}/adminLegacy/save.php",
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": edit_url,
        },
        timeout=60,
        verify=False,
        allow_redirects=True,
    )
    save.raise_for_status()
    return {"id": page_id, "title": page["title"], "status": str(save.status_code), "final_url": save.url}


def visible_text(session: requests.Session, base_url: str, slug: str) -> str:
    response = session.get(f"{base_url}/{slug}/?codex_page_verify=1", timeout=60)
    response.raise_for_status()
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", response.text))
    return html.unescape(text)


def main() -> int:
    env = load_env()
    base_url = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    login = env.get("HOROSHOP_LOGIN", "").strip()
    password = env.get("HOROSHOP_PASS", "").strip()
    if not login or not password:
        raise RuntimeError("HOROSHOP_LOGIN/HOROSHOP_PASS are missing in .env")

    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-content-pages/1.0"
    auth = session.post(
        f"{base_url}/core-api/admin/security/login",
        json={"login": login, "password": password},
        timeout=60,
        verify=False,
    )
    auth.raise_for_status()

    updated = [update_page(session, base_url, page_id, page) for page_id, page in PAGES.items()]
    verification = {}
    for page in PAGES.values():
        text = visible_text(session, base_url, page["slug"])
        verification[page["slug"]] = {
            "has_demo_text": "демонстраційний магазин" in text.lower(),
            "has_phone": "067 895-73-71" in text,
            "has_h1": page["h1"] in text,
        }

    report = {"base_url": base_url, "updated": updated, "verification": verification}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
