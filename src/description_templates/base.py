from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class DescriptionContext:
    family: str
    display_name: str
    brand: str
    type_word: str
    source_category: str
    name_raw: str
    common_params: dict[str, str]
    delta_params: dict[str, str]
    test_min: float | None
    test_max: float | None
    length_m: float | None
    action: str | None
    variant_count: int
    article: str = ""

    @classmethod
    def from_meta(cls, meta: dict) -> "DescriptionContext":
        return cls(
            article=str(meta.get("article") or ""),
            family=str(meta.get("family") or "other"),
            display_name=str(meta.get("display_name") or meta.get("name_raw") or "Рибальський товар"),
            brand=str(meta.get("brand") or ""),
            type_word=str(meta.get("type_word") or "Рибальський товар"),
            source_category=str(meta.get("source_category") or ""),
            name_raw=str(meta.get("name_raw") or ""),
            common_params={str(k): str(v) for k, v in (meta.get("common_params") or {}).items() if str(v).strip()},
            delta_params={str(k): str(v) for k, v in (meta.get("delta_params") or {}).items() if str(v).strip()},
            test_min=meta.get("test_min"),
            test_max=meta.get("test_max"),
            length_m=meta.get("length_m"),
            action=str(meta.get("action") or "").strip() or None,
            variant_count=int(meta.get("variant_count") or 1),
        )

    def seed(self) -> str:
        # артикул гарантує унікальний сід для кожного товару:
        # варіанти однієї моделі отримують РІЗНІ комбінації фраз
        base = self.name_raw or self.display_name
        return f"{base}|{self.article}" if self.article else base

    def param(self, *keys: str) -> str:
        for key in keys:
            value = self.common_params.get(key) or self.delta_params.get(key)
            if value:
                return value
        return ""

    def variant_marker(self) -> str:
        parts: list[str] = []
        if self.test_min is not None and self.test_max is not None:
            parts.append(f"кастинг {self.test_min:g}-{self.test_max:g} г")
        if self.length_m is not None:
            parts.append(f"довжина {self.length_m:g} м")
        if self.action:
            parts.append(f"лад {self.action}")
        for key in ("Діаметр", "Вага", "Об'єм", "Розмір", "Розривне навантаження"):
            value = self.delta_params.get(key)
            if value:
                parts.append(f"{key.lower()} {value}")
        return ", ".join(parts)


_VALUE_TRANSLATIONS = {
    "carbon": "карбон",
    "carbon fiber": "карбон",
    "composite": "композит",
    "fiberglass": "скловолокно",
}


def normalize_param_value(label: str, value: str) -> str:
    """Прибирає англомовні залишки зі значень і додає одиниці там, де їх бракує."""
    import re as _re
    value = value.strip()
    translated = _VALUE_TRANSLATIONS.get(value.lower())
    if translated:
        value = translated
    else:
        # складені значення на кшталт "carbon im6" / "carbon/im12" -> "карбон IM6"
        value = _re.sub(r"\bcarbon\b", "карбон", value, flags=_re.IGNORECASE)
        value = _re.sub(r"[/\s]*\bim\s?(\d+)\b", lambda m: f" IM{m.group(1)}", value, flags=_re.IGNORECASE).strip()
    # Кастинг "10-30" без одиниць -> "10-30 г"
    if label == "Кастинг" and value and not value[-1].isalpha():
        value = f"{value} г"
    return value


def pick(seed: str, options: list[str]) -> str:
    """Детермінований вибір варіанту фрази за hash товару — без random,
    щоб однаковий товар завжди отримував той самий текст між прогонами."""
    if not options:
        return ""
    if len(options) == 1:
        return options[0]
    digest = hashlib.md5(seed.encode("utf-8", "ignore")).digest()
    return options[digest[0] % len(options)]


def pick2(seed: str, options: list[str]) -> str:
    """Другий незалежний вибір з іншого байта хешу (для другого абзацу)."""
    if not options:
        return ""
    if len(options) == 1:
        return options[0]
    digest = hashlib.md5(seed.encode("utf-8", "ignore")).digest()
    return options[digest[1] % len(options)]


def _spec_sentence(ctx: DescriptionContext) -> str:
    """Вплітає 2-3 реальні параметри товару в живе речення.
    Дає унікальність тексту навіть у межах однієї серії."""
    bits: list[str] = []
    if ctx.length_m is not None and ctx.test_min is not None and ctx.test_max is not None:
        bits.append(
            f"Довжина {ctx.length_m:g} м у парі з тестом {ctx.test_min:g}-{ctx.test_max:g} г"
        )
    elif ctx.length_m is not None:
        bits.append(f"Робоча довжина — {ctx.length_m:g} м")
    diameter = ctx.param("Діаметр")
    load = ctx.param("Розривне навантаження")
    if diameter and load:
        bits.append(f"діаметр {diameter} витримує до {load}")
    weight = ctx.param("Вага")
    size = ctx.param("Розмір", "Гачок, №", "PE")
    material = ctx.param("Матеріал", "Матеріал бланка")
    if size and not bits:
        bits.append(f"розмір {size}")
    if weight and len(bits) < 2:
        bits.append(f"вага {weight}")
    if material and len(bits) < 2:
        material = normalize_param_value("Матеріал", material)
        if any(ch.isdigit() for ch in material):
            bits.append(f"матеріал {material}")
        else:
            bits.append(f"матеріал — {material.lower()}")
    if not bits:
        return ""
    sentence = ", ".join(bits)
    sentence = sentence[0].upper() + sentence[1:]
    tails = [
        " — параметри, що визначають робочий діапазон цієї моделі.",
        " — ключові цифри, на які варто орієнтуватися при підборі.",
        " — характеристики, з якими модель розкривається найкраще.",
        ".",
    ]
    return sentence + pick(ctx.seed() + "|spec", tails)


_CLOSING_POOL = [
    "Товар з наявності на нашому складі: відправляємо по Україні Новою поштою, на складні "
    "питання щодо сумісності зі снастями відповідаємо до замовлення.",
    "Перед відправкою комплектацію перевіряємо. Якщо сумніваєтесь у виборі розміру чи "
    "варіанта — напишіть нам, підкажемо під ваші умови ловлі.",
    "Відправка по Україні у день замовлення або наступного робочого дня. Питання щодо "
    "застосування — телефонуйте, з радістю проконсультуємо.",
    "У каталозі є суміжні позиції цієї ж серії: різні розміри та варіанти зручно порівняти "
    "за характеристиками нижче.",
    "Якщо потрібна допомога з підбором під конкретну водойму чи рибу — менеджер магазину "
    "на зв'язку у робочий час.",
    "Замовлення комплектуємо акуратно: дрібні елементи пакуємо так, щоб вони доїхали цілими "
    "у будь-який куточок України.",
]


def build_standard_description(
    ctx: DescriptionContext,
    intro: str | list[str],
    usage: str | list[str],
    bullets: list[str],
    closing: str | list[str] | None = None,
) -> str:
    """Збирає опис у стилі еталонних магазинів:
    1) конкретне позиціонування товару; 2) застосування/конструкція;
    3) речення з реальними параметрами; 4) короткий список характеристик;
    5) варіативне завершення (не на кожному товарі).
    Жодних однакових на весь каталог абзаців і службових рядків."""
    seed = ctx.seed()
    intro_text = pick(seed + "|intro", intro if isinstance(intro, list) else [intro])
    usage_text = pick2(seed + "|usage", usage if isinstance(usage, list) else [usage])

    label_aliases = {
        "Тест": "Кастинг",
        "Кастинг-тест": "Кастинг",
    }
    feature_items: list[str] = []
    seen_labels: set[str] = set()
    for key in bullets:
        value = ctx.common_params.get(key) or ctx.delta_params.get(key)
        if value:
            label = label_aliases.get(key, key)
            if label in seen_labels:
                continue
            seen_labels.add(label)
            value = normalize_param_value(label, value)
            feature_items.append(f"<li><strong>{label}:</strong> {value}</li>")

    paragraphs: list[str] = [f"<p>{intro_text}</p>"]
    if usage_text:
        paragraphs.append(f"<p>{usage_text}</p>")
    spec = _spec_sentence(ctx)
    if spec:
        paragraphs.append(f"<p>{spec}</p>")

    if closing is None:
        closing_pool = _CLOSING_POOL
    elif isinstance(closing, list):
        closing_pool = closing
    else:
        closing_pool = [closing]
    closing_text = pick(seed + "|closing", closing_pool)
    if closing_text:
        paragraphs.append(f"<p>{closing_text}</p>")

    html = "".join(paragraphs)
    if feature_items:
        html += f"<ul>{''.join(feature_items)}</ul>"
    return html
