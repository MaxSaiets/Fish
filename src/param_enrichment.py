"""
Масове збагачення характеристик товарів (2026-07-01).

Мета: у кожного товару багато КОРЕКТНИХ характеристик, а не пара.
Джерела — тільки те, що можна довести:
  1. Бренд (як окрема характеристика).
  2. Країна-виробник — лише для впевнено відомих брендів (map).
  3. Витяжка з НАЗВИ: кількість в упаковці, розмір/№, колір, вага, діаметр, довжина.
  4. Сімейні дефолти (Вид риболовлі / Сезон / Матеріал) — захищені узагальнення.

Нічого не вигадуємо: якщо ознаки в назві немає і бренд невідомий — поле не додаємо.
"""
from __future__ import annotations

import re

# --- Країна-виробник: лише впевнені бренди ---
_UA = "Україна"
BRAND_COUNTRY = {
    # Українські бренди/виробники
    "fanatik": _UA, "bounty": _UA, "profmontazh": _UA, "rpf": _UA, "orange": _UA,
    "puhach baits": _UA, "interkril": _UA, "realfish": _UA, "real fish": _UA,
    "herabunafishing": _UA, "anvifishing": _UA, "anvi": _UA, "3k baits": _UA,
    "fishing mix": _UA, "duralure": _UA, "breeze": _UA, "select": _UA,
    "favorite": _UA, "brain": _UA, "flagman": _UA, "gc": _UA, "golden catch": _UA,
    "fish sport": _UA, "boya by": _UA, "boya": _UA, "eos": _UA, "sams fish": _UA, "wiser": _UA,
    "carp master": _UA, "royal fish": _UA, "boom": _UA,
    # Польща
    "jaxon": "Польща", "dragon": "Польща", "mistrall": "Польща", "kamatsu": "Польща",
    "robinson": "Польща", "konger": "Польща",
    # Японія
    "keitech": "Японія", "owner": "Японія", "shimano": "Японія", "daiwa": "Японія",
    "yamatoyo": "Японія",
    # інші
    "mepps": "Франція", "lucky john": "Латвія", "carp expert": "Угорщина",
    "strike pro": "Швеція", "kaida": "Китай", "feima": "Китай", "weida": "Китай",
    "mifine": "Китай", "wist": "Китай",
    "garbolino": "Франція",
    # додано за дослідженням 2026-07-10 (generic імпортні бренди, підтверджено пошуком)
    "kalipso": "Китай", "siweida": "Китай", "winner": "Китай", "nikoma": "Китай",
}

# --- кольори у назві ---
_COLORS = {
    "чорний": ["чорн", "black", "bl "], "білий": ["біл", "white", "white"],
    "червоний": ["червон", "red"], "жовтий": ["жовт", "yellow"],
    "зелений": ["зелен", "green", "olive", "оливк"], "синій": ["син", "blue"],
    "срібний": ["срібн", "silver", "срібло"], "золотий": ["золот", "gold"],
    "помаранчевий": ["помаранч", "orange", "оранж"], "рожевий": ["рожев", "pink"],
    "прозорий": ["прозор", "clear", "crystal"], "коричневий": ["коричн", "brown"],
    "фіолетовий": ["фіолет", "violet", "purple"], "флуо": ["флуо", "fluo", "флюо"],
}

_PACK_RE = re.compile(r"(\d+)\s*(?:шт|штук|pcs|pc|уп)\.?\b", re.IGNORECASE)
_PACK_PAREN_RE = re.compile(r"\(\s*(\d{1,3})\s*\)")
_SIZE_HASH_RE = re.compile(r"(?:№|#|N|р\.?|розм\.?|size)\s*([0-9]{1,3}(?:/0)?(?:[.,]\d)?)", re.IGNORECASE)
_WEIGHT_RE = re.compile(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(?:g|gr|гр|г)\b", re.IGNORECASE)
_WEIGHT_KG_RE = re.compile(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(?:кг|kg)\b", re.IGNORECASE)
_DIAM_RE = re.compile(r"(?:ø|d|діам\.?|диам\.?)?\s*(0[.,]\d{2,3})\s*(?:мм|mm)?\b", re.IGNORECASE)
_DIAM_MM_RE = re.compile(r"(?<![\d.,])(\d{1,2}(?:[.,]\d)?)\s*(?:мм|mm)\b", re.IGNORECASE)
_LEN_M_RE = re.compile(r"(?<![\d.,])(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:м|m)\b", re.IGNORECASE)
_LEN_CM_RE = re.compile(r"(?<![\d.,])(\d{2,3})\s*(?:см|cm)\b", re.IGNORECASE)
_VOL_RE = re.compile(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(?:мл|ml)\b", re.IGNORECASE)
_VOL_L_RE = re.compile(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(?:л|l)\b", re.IGNORECASE)
_BATTERY_RE = re.compile(r"\b(AAA|AA|CR\d{3,4}|LR\d{1,4}|AG\d{1,2}|18650|D|C)\b")
_ROD_COUNT_RE = re.compile(r"на\s*(\d)\s*(?:вуд|виход|род)", re.IGNORECASE)
_HOOK_NO_RE = re.compile(r"гач(?:ок|\.)?\s*№?\s*(\d{1,2})", re.IGNORECASE)

# форма грузила з назви
_WEIGHT_SHAPES = {
    "куля": ["куля", "куль", "шар"], "груша": ["груш"], "ложка": ["ложк"],
    "оливка": ["олив"], "пласке": ["пласк", "плоск"], "тірольська паличка": ["тірол", "тирол"],
    "кормак": ["кормак", "кормушк"], "чебурашка": ["чебурашк"],
}
# покриття гачків з назви
_HOOK_COATINGS = {
    "чорний нікель (BN)": [" bn", "bn)", "black nickel"], "нікель": ["nickel", " ni "],
    "золотий": ["gold", "золот"], "тефлон": ["teflon", "тефлон"],
}
# тип PVA
_PVA_TYPES = {
    "сітка": ["сітк", "сетк", "mesh"], "стік": ["стік", "stick", "стик"],
    "стрічка": ["стрічк", "лента", "tape"], "пакет": ["пакет", "bag"],
    "нитка": ["нитк", "string"],
}
# матеріал кивка
_NOD_MATERIALS = {
    "лавсан": ["лавсан"], "металевий": ["метал", "сталь"], "силіконовий": ["силікон"],
    "пружинний": ["пружин"],
}


def _has(seen: set, name: str) -> bool:
    return name in seen


def country_for_brand(brand: str) -> str:
    if not brand:
        return ""
    return BRAND_COUNTRY.get(brand.strip().lower(), "")


def color_from_title(title_l: str) -> str:
    for canon, needles in _COLORS.items():
        for n in needles:
            if n in title_l:
                return canon
    return ""


# сім'ї, де важить розмір-номер (гачки, вертлюги, грузила...)
_SIZE_FAMILIES = {"hook", "swivel", "jig_head", "weight", "rigging", "ready_leader"}
# сім'ї, де важить упаковка
_PACK_FAMILIES = {"hook", "swivel", "silicone_lure", "ready_leader", "rigging",
                  "weight", "float", "pop_up_bait", "jig_head", "bait_mix"}
# сім'ї, де важить вага приманки
_WEIGHT_FAMILIES = {"spinner", "jig_winter", "balancer", "wobbler", "weight",
                    "silicone_lure", "jig_head", "feeder"}

# додаткові сімейні дефолти (захищені узагальнення)
_FAMILY_EXTRA = {
    "hook": {"Вид риболовлі": "Універсальна", "Матеріал": "Загартована сталь"},
    "spinner": {"Вид риболовлі": "Спінінг", "Вид риби": "Хижа"},
    "wobbler": {"Вид риболовлі": "Спінінг", "Вид риби": "Хижа"},
    "silicone_lure": {"Вид риболовлі": "Спінінг / джиг", "Вид риби": "Хижа"},
    "balancer": {"Вид риболовлі": "Зимова", "Вид риби": "Хижа", "Сезон": "Зима"},
    "jig_winter": {"Вид риболовлі": "Зимова", "Сезон": "Зима"},
    "reel": {"Вид риболовлі": "Спінінг / фідер"},
    "spinning": {"Вид риби": "Хижа", "Матеріал бланка": "Карбон / композит"},
    "feeder": {"Вид риболовлі": "Фідерна"},
    "float_rod": {"Вид риболовлі": "Поплавкова"},
    "boilie": {"Вид риби": "Короп / короповий"},
    "pop_up_bait": {"Вид риби": "Короп / короповий"},
    "pellets": {"Вид риби": "Короп / короповий"},
    "grain_bait": {"Вид риби": "Короп / білий"},
    "groundbait": {"Вид риби": "Короп / білий"},
    "boilie_": {},
    "hook_": {},
    "float": {"Вид риболовлі": "Поплавкова"},
    "weight": {"Вид риболовлі": "Донна / фідерна"},
    "landing_net": {"Матеріал сітки": "Безвузлова"},
    "keepnet": {"Матеріал сітки": "Безвузлова"},
    "clothing": {"Сезон": "Всесезонний"},
    "chair": {"Призначення": "Риболовля та кемпінг"},
    "bite_indicator": {"Вид риболовлі": "Коропова / фідерна"},
    "fluorocarbon": {"Матеріал": "Флюорокарбон", "Призначення": "Повідцевий матеріал"},
    "line": {},
    # підсилення найслабших сімей (захищені узагальнення)
    "rod_rest_accessory": {"Вид риболовлі": "Коропова / фідерна", "Матеріал": "Метал"},
    "tools": {"Сегмент": "Інструменти рибалки"},
    "jig_head": {"Вид риболовлі": "Спінінг / джиг", "Матеріал": "Свинець", "Вид риби": "Хижа"},
    "nod": {"Вид риболовлі": "Зимова / бортова", "Сезон": "Зима"},
    "pva_material": {"Вид риболовлі": "Коропова", "Особливість": "Водорозчинний"},
    "liquid_attractant": {"Вид риби": "Короп / білий", "Форма випуску": "Рідина"},
    "chair": {"Призначення": "Риболовля та кемпінг", "Складана конструкція": "Так"},
    "ready_rig": {"Вид риболовлі": "Коропова / фідерна"},
    "swivel": {"Сегмент": "Риболовна фурнітура"},
    "bag": {"Сегмент": "Зберігання та транспортування"},
    "tackle_box": {"Сегмент": "Зберігання та транспортування"},
    "weight_extra_": {},
    "ready_leader": {"Вид риболовлі": "Фідерна / донна"},
    "keepnet": {"Матеріал сітки": "Безвузлова", "Вид риболовлі": "Поплавкова / фідерна"},
    "float": {"Вид риболовлі": "Поплавкова", "Сезон": "Відкрита вода"},
    "hook_extra_": {},
    "battery": {"Сегмент": "Живлення електроніки"},
    "camping_fuel": {"Сегмент": "Туризм і кемпінг"},
    "gift_certificate": {"Форма": "Подарункова картка", "Термін дії": "Без обмежень"},
    "other": {"Сегмент": "Рибальські аксесуари"},
}


def enrich(family: str, title: str, brand: str, params: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Повертає розширений список (name, value). Нічого не перезаписує вже наявне."""
    out = list(params)
    seen = {n for n, _ in out}
    title_l = " " + re.sub(r"\s+", " ", title).lower() + " "

    def push(name: str, value: str) -> None:
        value = (value or "").strip()
        if name and value and name not in seen:
            out.append((name, value))
            seen.add(name)

    # 1. Бренд як характеристика
    if brand and brand.lower() not in {"без бренду", "no name", "noname", "-"}:
        push("Бренд", brand)

    # 2. Країна-виробник за брендом
    push("Країна-виробник", country_for_brand(brand))

    # 3. Витяжка з назви
    if family in _PACK_FAMILIES and "Кількість в упаковці" not in seen:
        m = _PACK_RE.search(title) or _PACK_PAREN_RE.search(title)
        if m:
            n = m.group(1)
            if n.isdigit() and 1 <= int(n) <= 500:
                push("Кількість в упаковці", f"{n} шт")

    if family in _SIZE_FAMILIES and "Розмір" not in seen and "Розмір гачка" not in seen:
        m = _SIZE_HASH_RE.search(title)
        if m:
            push("Розмір", f"№{m.group(1)}")

    if family in _WEIGHT_FAMILIES and "Вага" not in seen:
        m = _WEIGHT_RE.search(title)
        if m:
            push("Вага", f"{m.group(1).replace(',', '.')} г")

    if "Колір" not in seen:
        col = color_from_title(title_l)
        if col:
            push("Колір", col)

    # 3б. Цільові екстрактори для слабких сімей
    def first(rx):
        m = rx.search(title)
        return m.group(1).replace(",", ".") if m else ""

    def keyword_value(mapping: dict) -> str:
        for canon, needles in mapping.items():
            if any(n in title_l for n in needles):
                return canon
        return ""

    if family in {"liquid_attractant", "camping_fuel", "bait_mix", "foam_paste", "groundbait"} and "Об'єм" not in seen:
        v = first(_VOL_RE)
        if v:
            push("Об'єм", f"{v} мл")
        else:
            vl = first(_VOL_L_RE)
            if vl and float(vl) <= 20:
                push("Об'єм", f"{vl} л")

    if family in {"groundbait", "pellets", "boilie", "grain_bait", "pop_up_bait", "foam_paste"} and "Вага" not in seen:
        kg = first(_WEIGHT_KG_RE)
        if kg:
            push("Вага", f"{kg} кг")
        else:
            g = first(_WEIGHT_RE)
            if g:
                push("Вага", f"{g} г")

    if family in {"boilie", "pop_up_bait", "pellets", "pva_material"} and "Діаметр" not in seen:
        mm = first(_DIAM_MM_RE)
        if mm and float(mm) <= 40:
            push("Діаметр", f"{mm} мм")

    if family == "battery" and "Типорозмір" not in seen:
        m = _BATTERY_RE.search(title.upper())
        if m:
            push("Типорозмір", m.group(1))

    if family == "pva_material" and "Тип ПВА" not in seen:
        push("Тип ПВА", keyword_value(_PVA_TYPES))

    if family == "nod":
        push("Матеріал", keyword_value(_NOD_MATERIALS))
        cm = first(_LEN_CM_RE)
        if cm and "Довжина" not in seen:
            push("Довжина", f"{cm} см")

    if family == "weight" and "Форма грузила" not in seen and "Форма" not in seen:
        push("Форма грузила", keyword_value(_WEIGHT_SHAPES))

    if family == "hook" and "Покриття" not in seen:
        push("Покриття", keyword_value(_HOOK_COATINGS))

    if family in {"ready_rig", "ready_leader"} and "Розмір гачка" not in seen:
        hn = first(_HOOK_NO_RE)
        if hn:
            push("Розмір гачка", f"№{hn}")

    if family == "rod_rest_accessory":
        rc = first(_ROD_COUNT_RE)
        if rc:
            push("Кількість вудилищ", rc)
        cm = first(_LEN_CM_RE)
        if cm and "Довжина" not in seen:
            push("Довжина", f"{cm} см")
        else:
            m_len = first(_LEN_M_RE)
            if m_len and "Довжина" not in seen and float(m_len) <= 3:
                push("Довжина", f"{m_len} м")

    if family in {"jig_head", "swivel"} and "Розривне навантаження" not in seen:
        kg = first(_WEIGHT_KG_RE)
        if kg and family == "swivel":
            push("Розривне навантаження", f"{kg} кг")

    if family in {"keepnet", "landing_net", "rod_tube", "chair", "tools"} and "Довжина" not in seen:
        m_len = first(_LEN_M_RE)
        cm = first(_LEN_CM_RE)
        if m_len and float(m_len) <= 5:
            push("Довжина", f"{m_len} м")
        elif cm:
            push("Довжина", f"{cm} см")

    if family == "gift_certificate" and "Номінал" not in seen:
        m = re.search(r"(\d{3,5})\s*(?:грн|uah)?", title)
        if m and 100 <= int(m.group(1)) <= 20000:
            push("Номінал", f"{m.group(1)} грн")

    # 4. Сімейні дефолти
    for k, v in _FAMILY_EXTRA.get(family, {}).items():
        push(k, v)

    # 5. Санітизація якості (виправлення сміття перед віддачею)
    return _sanitize_params(out)


_LATIN_JUNK_RE = re.compile(r"^[A-Za-z]{3,}$")
_SIZE_NAMES = {"Розмір", "Розмір/№", "Типорозмір", "Розмір гачка"}

# прапорець для діагностики: вимкнути санітизацію, щоб порівняти «до/після»
SANITIZE_ENABLED = True


def _sanitize_params(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Прибирає типові дефекти: латинське слово-сміття у полях розміру
    (CARP, LITH…) і дублювання «Тип»/«Тип X» з однаковим значенням."""
    if not SANITIZE_ENABLED:
        return pairs
    cleaned: list[tuple[str, str]] = []
    for n, v in pairs:
        val = (v or "").strip()
        # латинське слово без цифр у полі розміру — це не розмір (S/L/XL ≤2 символи лишаються)
        if n in _SIZE_NAMES and _LATIN_JUNK_RE.match(val):
            continue
        cleaned.append((n, v))
    base_type = next((str(v).strip() for n, v in cleaned if n == "Тип"), None)
    if base_type:
        result: list[tuple[str, str]] = []
        for n, v in cleaned:
            if n != "Тип" and n.startswith("Тип ") and str(v).strip() == base_type:
                continue  # «Тип повідця»=«Тип» → надлишок, прибираємо
            result.append((n, v))
        cleaned = result
    return cleaned
