from __future__ import annotations

import re
from dataclasses import dataclass, field

SKIP_NAMES = {"Повна назва товару", "test", "tetg", "Мій товар"}
PLACEHOLDER_CATEGORIES = {"Ваш тип товарів чи послуг", "Ваша група товарів чи послуг", "Нова група"}

LENGTH_M_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:m|м)\b", re.IGNORECASE)
LENGTH_CM_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*см\b", re.IGNORECASE)
DIAMETER_MM_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*mm\b", re.IGNORECASE)
VOLUME_ML_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*мл\b|(\d+(?:[.,]\d+)?)\s*ml\b", re.IGNORECASE)
WEIGHT_G_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:г|гр|g)\b", re.IGNORECASE)
KG_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*kg\b", re.IGNORECASE)
LB_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*lb\b", re.IGNORECASE)
PE_RE = re.compile(r"#\s*(\d+(?:[.,]\d+)?)")
PACK_QTY_RE = re.compile(r"(\d+)\s*шт\b", re.IGNORECASE)
HOOK_SIZE_RE = re.compile(r"№\s*([A-Za-zА-Яа-я0-9./+-]+)")
TEST_RANGE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*[-–]\s*(\d+(?:[.,]\d+)?)")
ACTION_WORD_RE = re.compile(r"\b(Extra\s*Fast|Ex\.?\s*Fast|Fast|Moderate|Medium|Slow)\b", re.IGNORECASE)
ACTION_NUM_RE = re.compile(r"(\d+)\s*стрій", re.IGNORECASE)
DIMENSION_RE = re.compile(r"d\s*(\d+(?:[.,]\d+)?)\s*[*xх]\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
QUOTED_BRAND_RE = re.compile(r'"([^"]+)"')

FAMILY_LABELS = {
    "spinning": "Спінінг",
    "float_rod": "Вудка",
    "grain_bait": "Зернова насадка",
    "boilie": "Бойли",
    "pop_up_bait": "Поп-ап",
    "pellets": "Пелетс",
    "bait_mix": "Мікс",
    "liquid_attractant": "Ліквід",
    "line": "Волосінь",
    "fluorocarbon": "Флюрокарбон",
    "shock_leader": "Шок-лідер",
    "ready_leader": "Повідець",
    "nod": "Кивок",
    "bite_indicator": "Сигналізатор клювання",
    "rod_rest_accessory": "Аксесуар для підставки",
    "other": "Рибальський товар",
}

DEFAULT_COMMON_PARAMS = {
    "spinning": {"Тип вудилища": "Спінінг"},
    "float_rod": {"Тип вудилища": "Махова / херабуна"},
    "grain_bait": {"Тип насадки": "Зернова", "Призначення": "Коропова риболовля"},
    "boilie": {"Тип насадки": "Бойли", "Призначення": "Коропова риболовля"},
    "pop_up_bait": {"Тип насадки": "Поп-ап", "Плавучість": "Плаваюча"},
    "pellets": {"Тип насадки": "Пелетс / гранула", "Призначення": "Коропова риболовля"},
    "bait_mix": {"Тип суміші": "Мікс / стік-мікс", "Призначення": "ПВА / закорм"},
    "liquid_attractant": {"Тип атрактанту": "Ліквід"},
    "line": {"Тип": "Монофільна волосінь"},
    "fluorocarbon": {"Тип": "Флюрокарбон"},
    "shock_leader": {"Тип": "Шок-лідер"},
    "ready_leader": {"Тип": "Готовий повідець"},
    "nod": {"Тип": "Кивок"},
    "bite_indicator": {"Тип": "Сигналізатор клювання"},
    "rod_rest_accessory": {"Тип": "Аксесуар для підставки"},
    "other": {},
}

SOURCE_CATEGORY_RULES = [
    ("вудки", ("Вудки",), "float_rod"),
    ("бойли поп", ("Поп-ап насадки",), "pop_up_bait"),
    ("поп ап", ("Поп-ап насадки",), "pop_up_bait"),
    ("бойли", ("Бойли",), "boilie"),
    ("зернов", ("Зернові",), "grain_bait"),
    ("пелетс", ("Пелетс та гранула",), "pellets"),
    ("гранула", ("Пелетс та гранула",), "pellets"),
    ("мікс", ("Мікси та стік-мікси",), "bait_mix"),
    ("стік", ("Мікси та стік-мікси",), "bait_mix"),
    ("ліквад", ("Ліквіди",), "liquid_attractant"),
    ("ліквід", ("Ліквіди",), "liquid_attractant"),
    ("шоклідер", ("Шок-лідер",), "shock_leader"),
    ("кивок", ("Кивки",), "nod"),
    ("сигнал", ("Сигналізатори",), "bite_indicator"),
    ("свінгер", ("Сигналізатори",), "bite_indicator"),
    ("механічні", ("Сигналізатори",), "bite_indicator"),
    ("аксесуари для підставки", ("Аксесуари для підставки",), "rod_rest_accessory"),
]


@dataclass
class ParsedProduct:
    family: str
    type_word: str
    brand: str
    model_name: str
    display_name: str
    common_params: dict[str, str] = field(default_factory=dict)
    delta_params: dict[str, str] = field(default_factory=dict)
    test_min: float | None = None
    test_max: float | None = None
    length_m: float | None = None
    action: str | None = None


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def parse_float(raw: str | float | int | None) -> float | None:
    if raw in (None, ""):
        return None
    try:
        return float(str(raw).replace(",", "."))
    except ValueError:
        return None


def normalize_key(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", "_", text).strip("_")


def last_real_category(category_path: list[str] | None) -> str:
    items = [normalize_spaces(item) for item in (category_path or []) if normalize_spaces(item)]
    items = [item for item in items if item not in PLACEHOLDER_CATEGORIES]
    return items[-1] if items else ""


def get_source_category(stem: str, sample_names: list[str] | None = None) -> tuple[tuple[str, ...], str]:
    normalized = normalize_spaces(stem).lower()
    for needle, path, family in SOURCE_CATEGORY_RULES:
        if needle in normalized:
            return path, family

    sample = " ".join(sample_names or []).lower()
    if "флюрокарбон" in sample:
        return ("Флюрокарбон",), "fluorocarbon"
    if "повідець" in sample or "поводок" in sample:
        return ("Повідці",), "ready_leader"
    if "волосінь" in sample or "ліска" in sample:
        return ("Волосінь",), "line"
    if "сигналізатор" in sample or "дзвіночок" in sample or "світлячок" in sample:
        return ("Сигналізатори",), "bite_indicator"
    return ("Інше",), "other"


def detect_family(name: str, category_path: list[str] | None = None) -> str:
    text = normalize_spaces(name).lower()
    categories = " | ".join((category_path or [])).lower()

    checks = [
        ("spinning", ["спінінг"], ["спінінг"]),
        ("float_rod", ["вудки"], ["вудка", "hera", "herabuna"]),
        ("shock_leader", ["шок-лідер", "шоклідер"], ["шоклідер", "shock leader"]),
        ("fluorocarbon", ["флюрокарбон"], ["флюрокарбон"]),
        ("line", ["волосінь"], ["волосінь", "ліска"]),
        ("ready_leader", ["повідці"], ["повідець", "поводок"]),
        ("grain_bait", ["зернові"], ["кукуруза", "кукурудза", "горіх", "corn"]),
        ("boilie", ["бойли"], ["бойл", "boilie"]),
        ("pop_up_bait", ["поп-ап насадки"], ["поп ап", "pop-up", "popup"]),
        ("pellets", ["пелетс та гранула"], ["пелетс", "pellets", "гранула"]),
        ("bait_mix", ["мікси та стік-мікси"], ["стік", "pva", "мікс"]),
        ("liquid_attractant", ["ліквіди"], ["ліквід", "liquid", "dip"]),
        ("nod", ["кивки"], ["кивок"]),
        ("rod_rest_accessory", ["аксесуари для підставки"], ["підставк"]),
        ("bite_indicator", ["сигналізатори"], ["сигналізатор", "свінгер", "дзвіночок", "світлячок"]),
    ]
    for family, cat_needles, text_needles in checks:
        if any(needle in categories for needle in cat_needles) or any(needle in text for needle in text_needles):
            return family
    return "other"


def pop_brand(text: str) -> tuple[str, str]:
    quoted = QUOTED_BRAND_RE.findall(text)
    if quoted:
        brand = normalize_spaces(quoted[-1])
        cleaned = normalize_spaces(QUOTED_BRAND_RE.sub("", text))
        return brand, cleaned
    return "", text


def extract_token(pattern: re.Pattern[str], text: str) -> tuple[re.Match[str] | None, str]:
    match = pattern.search(text)
    if not match:
        return None, text
    cleaned = normalize_spaces(text[:match.start()] + " " + text[match.end():])
    return match, cleaned


def family_brand_model(family: str, cleaned_name: str) -> tuple[str, str]:
    brand_from_quotes, cleaned = pop_brand(cleaned_name)
    if brand_from_quotes:
        return brand_from_quotes, normalize_spaces(cleaned)

    parts = cleaned.split()
    if not parts:
        return "", ""

    if family == "float_rod" and len(parts) > 1 and re.fullmatch(r"[A-Za-z][A-Za-z\s-]+", parts[-1]):
        brand = parts[-1]
        model = " ".join(parts[:-1])
        return normalize_spaces(brand), normalize_spaces(model)

    if family in {"spinning", "line", "fluorocarbon", "shock_leader"}:
        brand = parts[0]
        model = " ".join(parts[1:]) if len(parts) > 1 else parts[0]
        return normalize_spaces(brand), normalize_spaces(model)

    if family == "ready_leader" and len(parts) > 1:
        brand = parts[-1] if re.fullmatch(r"[A-Za-zА-Яа-я][\w.-]+", parts[-1]) else ""
        if brand:
            model = " ".join(parts[:-1])
            return normalize_spaces(brand), normalize_spaces(model)

    return "", normalize_spaces(cleaned)


def add_param(params: dict[str, str], key: str, value: object, suffix: str = "") -> None:
    if value in (None, "", 0):
        return
    if isinstance(value, float):
        text = f"{value:g}"
    else:
        text = str(value).strip()
    if not text:
        return
    params[key] = f"{text}{suffix}".strip()


def parse_product(product: dict) -> ParsedProduct | None:
    name = normalize_spaces(product.get("name", ""))
    if not name or name in SKIP_NAMES:
        return None

    category_path = [normalize_spaces(item) for item in product.get("category_path") or [] if normalize_spaces(item)]
    family = detect_family(name, category_path)
    type_word = FAMILY_LABELS.get(family, "Рибальський товар")
    base_name = name
    delta: dict[str, str] = {}
    common = dict(DEFAULT_COMMON_PARAMS.get(family, {}))

    test_match, base_name = extract_token(TEST_RANGE_RE, base_name)
    test_min = test_max = None
    if test_match:
        tmin = parse_float(test_match.group(1))
        tmax = parse_float(test_match.group(2))
        if tmin is not None and tmax is not None and tmax >= tmin:
            test_min, test_max = tmin, tmax

    action_match, base_name = extract_token(ACTION_WORD_RE, base_name)
    action_num_match = None
    action = None
    if action_match:
        action = normalize_spaces(action_match.group(1))
    else:
        action_num_match, base_name = extract_token(ACTION_NUM_RE, base_name)
        if action_num_match:
            action = normalize_spaces(action_num_match.group(1))

    length_m_match, base_name = extract_token(LENGTH_M_RE, base_name)
    length_cm_match = None
    length_m = None
    if length_m_match:
        length_m = parse_float(length_m_match.group(1))
    else:
        length_cm_match, base_name = extract_token(LENGTH_CM_RE, base_name)
        if length_cm_match and family in {"ready_leader", "bite_indicator"}:
            add_param(delta, "Довжина", parse_float(length_cm_match.group(1)), " см")
        elif length_cm_match:
            value = parse_float(length_cm_match.group(1))
            if value is not None:
                length_m = round(value / 100, 2)

    diameter_match, base_name = extract_token(DIAMETER_MM_RE, base_name)
    if diameter_match:
        add_param(delta, "Діаметр", parse_float(diameter_match.group(1)), " мм")

    volume_match, base_name = extract_token(VOLUME_ML_RE, base_name)
    if volume_match:
        value = volume_match.group(1) or volume_match.group(2)
        add_param(delta, "Об'єм", parse_float(value), " мл")

    weight_match, base_name = extract_token(WEIGHT_G_RE, base_name)
    if weight_match:
        add_param(delta, "Вага", parse_float(weight_match.group(1)), " г")

    kg_match, base_name = extract_token(KG_RE, base_name)
    if kg_match:
        add_param(delta, "Розривне навантаження", parse_float(kg_match.group(1)), " кг")

    lb_match, base_name = extract_token(LB_RE, base_name)
    if lb_match:
        add_param(delta, "Розривне навантаження (lb)", parse_float(lb_match.group(1)), " lb")

    pe_match, base_name = extract_token(PE_RE, base_name)
    if pe_match:
        add_param(delta, "PE", parse_float(pe_match.group(1)))

    pack_match, base_name = extract_token(PACK_QTY_RE, base_name)
    if pack_match:
        add_param(delta, "Кількість в упаковці", int(pack_match.group(1)), " шт")

    hook_match, base_name = extract_token(HOOK_SIZE_RE, base_name)
    if hook_match:
        add_param(delta, "Розмір", hook_match.group(1))

    dim_match, base_name = extract_token(DIMENSION_RE, base_name)
    if dim_match:
        add_param(delta, "Діаметр", parse_float(dim_match.group(1)), " мм")
        add_param(delta, "Довжина", parse_float(dim_match.group(2)), " мм")

    if length_m is not None:
        add_param(delta, "Довжина", length_m, " м")
    if test_min is not None and test_max is not None:
        delta["Тест"] = f"{test_min:g}-{test_max:g}"
    if action:
        delta["Стрій"] = action

    brand, model_name = family_brand_model(family, base_name)
    if not brand and family in {"grain_bait", "boilie", "pop_up_bait", "pellets", "bait_mix", "liquid_attractant"}:
        quoted = QUOTED_BRAND_RE.findall(name)
        if quoted:
            brand = quoted[-1]

    cleaned_for_flavor = normalize_spaces(base_name.replace(brand, "", 1) if brand else base_name)
    display_name = normalize_spaces(" ".join(part for part in [type_word, brand, model_name] if part))

    if family in {"grain_bait", "boilie", "pop_up_bait", "pellets", "bait_mix", "liquid_attractant"}:
        flavor_candidate = cleaned_for_flavor
        for marker in ["Тигровий Горіх", "Кукуруза Цукрова", "Кукурудза Цукрова", "Бойли", "Поп ап", "Поп-ап", "Пелетс", "Гранула", "Мікс", "Стік", "Ліквід"]:
            flavor_candidate = flavor_candidate.replace(marker, "").strip(" -")
        if flavor_candidate and len(flavor_candidate.split()) <= 4:
            common["Аромат"] = flavor_candidate

    if family == "line" and "фідер" in name.lower():
        common["Призначення"] = "Фідерна риболовля"
    if family == "fluorocarbon":
        common["Матеріал"] = "Флюрокарбон"
    if family == "shock_leader":
        common["Тип"] = "Шок-лідер"
    if family == "ready_leader":
        if "карпов" in name.lower():
            common["Призначення"] = "Карпова риболовля"
        if "флюрокарбон" in name.lower():
            common["Матеріал"] = "Флюрокарбон"
        if "wolfram" in name.lower():
            common["Матеріал"] = "Вольфрам"
    if family == "nod":
        if "лавсан" in name.lower():
            common["Матеріал"] = "Лавсан"
        if "зима" in name.lower():
            common["Сезон"] = "Зима / літо"
    if family == "bite_indicator":
        lowered = name.lower()
        if "світлячок" in lowered:
            common["Підтип"] = "Під світлячок"
        elif "свінгер" in lowered:
            common["Підтип"] = "Свінгер"
        elif "дзвіночок" in lowered:
            common["Підтип"] = "Дзвіночок"
        elif "механіч" in lowered:
            common["Підтип"] = "Механічний"

    return ParsedProduct(
        family=family,
        type_word=type_word,
        brand=normalize_spaces(brand),
        model_name=normalize_spaces(model_name or base_name),
        display_name=display_name or name,
        common_params=common,
        delta_params=delta,
        test_min=test_min,
        test_max=test_max,
        length_m=length_m,
        action=action,
    )
