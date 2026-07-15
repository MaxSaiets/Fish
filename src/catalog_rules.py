from __future__ import annotations

import re
from dataclasses import dataclass, field

SKIP_NAMES = {"Повна назва товару", "test", "tetg", "Мій товар"}
PLACEHOLDER_CATEGORIES = {"Ваш тип товарів чи послуг", "Ваша група товарів чи послуг", "Нова група", "Новая группа"}

# Довжина в метрах: тільки якщо число <= 30 (більше — це код вудилища типу 802M)
# Не матчимо після цифри одразу ML/MH/M (power class спінінгу)
LENGTH_M_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:m|м)\b(?!l\b|h\b|lh\b)", re.IGNORECASE)
LENGTH_CM_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*см\b", re.IGNORECASE)
DIAMETER_MM_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:mm|мм)\b", re.IGNORECASE)
# ml тільки якщо після немає букви (щоб не ловити 802ML-SP як 802мл)
VOLUME_ML_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*мл\b|(\d+(?:[.,]\d+)?)\s*ml(?![a-z])", re.IGNORECASE)
VOLUME_L_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:л|л\.)\b", re.IGNORECASE)
WEIGHT_G_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:г|гр|g)\b", re.IGNORECASE)
KG_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*kg\b", re.IGNORECASE)
LB_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*lb\b", re.IGNORECASE)
PE_RE = re.compile(r"#\s*(\d+(?:[.,]\d+)?)")
PACK_QTY_RE = re.compile(r"(\d+)\s*(?:шт|pc|pcs)\b", re.IGNORECASE)
ITEM_COUNT_RE = re.compile(r"(\d+)\s*(?:предм(?:ет[аів])?|предмет(?:и|ів)?|pcs?)\b", re.IGNORECASE)
HOOK_SIZE_RE = re.compile(r"(?:№|\bno\.?\b)\s*([A-Za-zА-Яа-я0-9./+-]+)", re.IGNORECASE)
HOOK_SLASH_RE = re.compile(r"\b(\d+)[/\\](\d+)\b")   # e.g. 2/0, 1\0
# Поглинаємо також одиницю після діапазону (г/g/lb/м/m тощо), щоб не залишалось orphan-символу
TEST_RANGE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*[-–]\s*(\d+(?:[.,]\d+)?)\s*(?:г|гр|g|lb|lbs|кг|kg|м|m|ft)?\b", re.IGNORECASE)
ACTION_WORD_RE = re.compile(r"\b(Extra\s*Fast|Ex\.?\s*Fast|Fast|Moderate|Medium|Slow)\b", re.IGNORECASE)
ACTION_NUM_RE = re.compile(r"(\d+)\s*стрій", re.IGNORECASE)
SECTIONS_RE = re.compile(r"(\d+)\s*сек", re.IGNORECASE)
VOLT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*v\b", re.IGNORECASE)
BATTERY_FORMAT_RE = re.compile(r"\b((?:6lr61|lr44|lr03|lr6|aaa|aa|cr2032|cr2025|cr2016))\b", re.IGNORECASE)
UAH_AMOUNT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*грн", re.IGNORECASE)
DIMENSION_RE = re.compile(r"d\s*(\d+(?:[.,]\d+)?)\s*[*xх]\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
DIMENSION_ANY_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*[*xх]\s*(\d+(?:[.,]\d+)?)(?:\s*[*xх]\s*(\d+(?:[.,]\d+)?))?\b", re.IGNORECASE)
QUOTED_BRAND_RE = re.compile(r'"([^"]+)"')
# Котушки: розмір (1000–20000)
REEL_SIZE_RE = re.compile(r"\b([1-9]\d{3})\b")
# Котушки: підшипники X+1
BEARING_RE = re.compile(r"\b(\d+)\s*[+]\s*1\b")
# Воблери/приманки: глибина занурення
WOBBLER_DEPTH_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*[-–]\s*(\d+(?:[.,]\d+)?)\s*(?:ft|m|м)\b", re.IGNORECASE)
# Розмір в дюймах (силіконові)
INCH_SIZE_RE = re.compile(r"""(\d+(?:[.,]\d+)?)\s*(?:"|''|inch|in\b)""", re.IGNORECASE)
# Розмір через пробіл тільки після слів Розмір/Size/S/M/L
SIZE_LETTER_RE = re.compile(r"\b(XS|XXS|S|M|L|XL|XXL|XXXL)\b")
# Матеріал мормишки
TUNGSTEN_RE = re.compile(r"\b(вольфрам|tungsten|wolf)\b", re.IGNORECASE)
# Лески: метраж
METERS_SPOOL_RE = re.compile(r"\b(\d+)\s*(?:м|m)\b", re.IGNORECASE)
# Флуоресцентна, плетена, монофільна
BRAID_RE = re.compile(r"\b(плетен|braid|шнур)\b", re.IGNORECASE)
FLUO_RE = re.compile(r"\b(флуоресц|fluoro|fluo)\b", re.IGNORECASE)

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
    "reel": "Котушка",
    "wobbler": "Воблер",
    "spinner": "Блешня",
    "silicone_lure": "Силіконова приманка",
    "jig_head": "Джиг-головка",
    "balancer": "Балансир",
    "jig_winter": "Мормишка",
    "hook": "Гачок",
    # Нові сімейства
    "float": "Поплавок",
    "feeder": "Годівниця",
    "landing_net": "Підсак",
    "keepnet": "Садок",
    "weight": "Вантаж/грузило",
    "swivel": "Вертлюг/застібка",
    "ready_rig": "Готовий монтаж",
    "pva_material": "ПВА матеріал",
    "groundbait": "Прикормка",
    "foam_paste": "Пінотісто/макуха",
    "tools": "Інструмент для риболовлі",
    "rod_tube": "Чохол/тубус",
    "chair": "Крісло/стілець",
    "clothing": "Одяг/взуття для риболовлі",
    "tackle_box": "Ящик/коробка для снастей",
    "bag": "Сумка рибальська",
    "rigging": "Монтажна оснастка",
    "gift_certificate": "Подарунковий сертифікат",
    "camping_fuel": "Паливо для туризму",
    "battery": "Батарейка",
    "flashlight": "Ліхтар",
    "other": "Рибальський товар",
}

DEFAULT_COMMON_PARAMS = {
    "spinning": {"Тип вудилища": "Спінінг"},
    "float_rod": {"Тип вудилища": "Махова"},
    "grain_bait": {"Тип насадки": "Зернова", "Призначення": "Коропова риболовля"},
    "boilie": {"Тип насадки": "Бойли", "Призначення": "Коропова риболовля"},
    "pop_up_bait": {"Тип насадки": "Поп-ап", "Плавучість": "Плаваюча"},
    "pellets": {"Тип насадки": "Пелетс / гранула", "Призначення": "Коропова риболовля"},
    "bait_mix": {"Тип суміші": "Мікс / стік-мікс", "Призначення": "ПВА / закорм"},
    "liquid_attractant": {"Тип атрактанту": "Ліквід"},
    "line": {"Тип": "Монофільна волосінь", "Матеріал": "Нейлон / PE", "Призначення": "Основна ліска / шнур"},
    "fluorocarbon": {"Тип": "Флюрокарбон"},
    "shock_leader": {"Тип": "Шок-лідер"},
    "ready_leader": {"Тип": "Готовий повідець"},
    "nod": {"Тип": "Кивок"},
    "bite_indicator": {"Тип": "Сигналізатор клювання", "Призначення": "Контроль клювання", "Сегмент": "Риболовні аксесуари"},
    "rod_rest_accessory": {"Тип": "Аксесуар для підставки"},
    "reel": {"Тип": "Безінерційна котушка", "Призначення": "Спінінгова / фідерна риболовля"},
    "wobbler": {"Тип": "Воблер"},
    "spinner": {"Тип": "Блешня"},
    "silicone_lure": {"Тип": "Силіконова приманка", "Призначення": "Спінінгова риболовля"},
    "jig_head": {"Тип": "Джиг-головка"},
    "balancer": {"Тип": "Балансир"},
    "jig_winter": {"Тип": "Мормишка"},
    "hook": {"Тип": "Гачок"},
    # Нові сімейства
    "float": {"Тип": "Поплавок", "Призначення": "Поплавкова ловля"},
    "feeder": {"Тип": "Годівниця", "Призначення": "Коропова/фідерна риболовля"},
    "landing_net": {"Тип": "Підсак", "Призначення": "Виважування риби"},
    "keepnet": {"Тип": "Садок", "Призначення": "Зберігання риби"},
    "weight": {"Тип": "Вантаж/грузило", "Матеріал": "Свинець", "Призначення": "Монтаж оснастки"},
    "swivel": {"Тип": "Вертлюг/застібка", "Призначення": "Монтаж оснастки"},
    "ready_rig": {"Тип": "Готовий монтаж", "Призначення": "Коропова риболовля", "Комплектація": "Готова оснастка"},
    "pva_material": {"Тип": "ПВА матеріал"},
    "groundbait": {"Тип насадки": "Прикормка", "Призначення": "Коропова риболовля"},
    "foam_paste": {"Тип насадки": "Пінотісто / макуха", "Форма": "Паста / пресована насадка", "Призначення": "Поплавкова та коропова риболовля"},
    "tools": {"Тип": "Інструмент для риболовлі", "Призначення": "Монтаж оснастки", "Матеріал": "Змішаний"},
    "rod_tube": {"Тип": "Чохол / тубус"},
    "chair": {"Тип": "Крісло/стілець", "Призначення": "Риболовля та кемпінг"},
    "clothing": {"Тип": "Одяг / аксесуар", "Призначення": "Риболовля", "Сезон": "Всесезонний"},
    "tackle_box": {"Тип": "Ящик / коробка для снастей", "Призначення": "Зберігання снастей"},
    "bag": {"Тип": "Сумка рибальська", "Призначення": "Зберігання та транспортування снастей"},
    "rigging": {"Тип": "Монтажна оснастка", "Призначення": "Монтаж оснастки", "Сегмент": "Риболовна фурнітура"},
    "gift_certificate": {"Тип": "Подарунковий сертифікат", "Призначення": "Подарунок рибалці"},
    "camping_fuel": {"Тип": "Паливо для туризму", "Призначення": "Кемпінг і відпочинок"},
    "battery": {"Тип": "Батарейка", "Призначення": "Живлення аксесуарів"},
    "flashlight": {"Тип": "Ліхтар", "Призначення": "Освітлення"},
    "other": {"Тип": "Рибальський товар", "Призначення": "Риболовля", "Сегмент": "Різне"},
}

GENERIC_LEADING_TOKENS = {
    "штек", "штек.", "штекер", "штекер.", "тел", "тел.", "телескоп", "телескопічний",
    "махова", "махове", "коропове", "фідерне", "болонське", "boat", "sec", "travel",
}

KNOWN_MULTIWORD_BRANDS = {
    "new hunter",
    "river tramp",
    "carp master",
    "fish sport",
    "lucky john",
    "team dubna",
    "black hole",
    "crazy fish",
    "real fish",
    "carp expert",
    "winner amazing",
    "royal fish",
    "foode fish",
    "boya by",
    "carp fishing",
    "vido craft",
    "blue bird",
    "strong wind",
    "fishing box",
    "tan look",
    "power feeder",
    "real madrid",
    "bulo composite",
    "extension bolognese",
    "maori fish",
    "master hooks",
    "fishing roi",
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
    if "сертиф" in sample:
        return ("Сертифікати",), "gift_certificate"
    if "повідець" in sample or "поводок" in sample:
        return ("Повідці",), "ready_leader"
    if "волосінь" in sample or "ліска" in sample:
        return ("Волосінь",), "line"
    if "сигналізатор" in sample or "дзвіночок" in sample or "світлячок" in sample:
        return ("Сигналізатори",), "bite_indicator"
    return ("Інше",), "other"


def detect_family(name: str, category_path: list[str] | None = None) -> str:  # noqa: C901
    text = normalize_spaces(name).lower()
    cats = " | ".join((category_path or [])).lower()

    strong_name_checks = [
        ("reel", ["катушка", "котушка"]),
        ("wobbler", ["воблер", "wobbler"]),
        ("spinner", ["блешня", "блесн", "mepps"]),
        ("balancer", ["балансир"]),
        ("jig_winter", ["мормишка", "мармишка"]),
        ("hook", ["офсетн", "трійник", "двійник", "гачок", "крючок"]),
        # "вудочка"/"махова" специфічніші за "спінінг": постачальники ліплять
        # "Спінінг Вудочка ..." на телескопічні вудки — це НЕ спінінг
        ("float_rod", ["вудочка", "вудка ", "махов", "без кілець", "б/к", "б\\к",
                       "болонез", "bolognese", "болонськ", "bolo "]),
        ("spinning", ["спінінг"]),
        ("keepnet", ["кукан"]),
        ("line", ["волосінь", "ліска", "шнур"]),
        ("ready_leader", ["повідець", "поводок"]),
        ("pop_up_bait", ["поп ап", "попап", "pop-up", "pop up", "popup"]),
        ("pellets", ["пелетс", "pellets"]),
        ("pva_material", ["пва сітка", "пва мішечок", "pva"]),
        ("float", ["поплавок"]),
        ("weight", ["вантаж", "грузило", "груз "]),
        ("swivel", ["вертлюг", "застібк"]),
        ("nod", ["кивок"]),
        ("landing_net", ["підсак"]),
        ("keepnet", ["садок"]),
        ("rod_tube", ["тубус", "чохол для вудилища"]),
        ("clothing", ["дощовик", "рукавиці", "термошкарпетки", "куртка риболов", "костюм риболов"]),
        ("gift_certificate", ["сертифікат", "сертифкат"]),
        ("camping_fuel", ["вугілля"]),
        ("battery", ["крона", "батарейка"]),
        ("flashlight", ["ліхтар", "ліхтарик"]),
    ]
    for family, text_kws in strong_name_checks:
        if any(kw in text for kw in text_kws):
            return family

    if re.search(r"\bтісто\b|\bpaste\b", text) and "herabuna" in text:
        return "foam_paste"

    if "bounty" in cats and "насадка" in cats:
        return "pop_up_bait"

    # Спочатку перевіряємо категорію (точніший сигнал), потім назву
    # Порядок важливий: конкретніші типи — раніше
    cat_checks = [
        # (family, cat_keywords)
        ("reel",             ["катушки", "котушки"]),
        ("wobbler",          ["воблер"]),
        ("spinner",          ["блесна", "блешні", "mepps", "тел-спіннер"]),
        ("balancer",         ["балансир"]),
        ("jig_winter",       ["мармишка", "мормишка"]),
        ("silicone_lure",    ["силіконова приманка", "силікон", "твістер", "віброхвіст", "рачок", "черв'як", "слаг", "мандула"]),
        ("hook",             ["гачки", "трійники", "офсетні", "двійники"]),
        ("spinning",         ["спінінги і вудки | спінінг", "спінінг"]),
        ("float_rod",        ["вудки", "вудочка", "махові", "херабуна | вудочка"]),
        ("shock_leader",     ["шоклідер", "шок-лідер"]),
        ("fluorocarbon",     ["флюрокарбон", "флюр"]),
        ("ready_leader",     ["повідці", "поводочний матеріал"]),
        ("line",             ["ліска", "волосінь", "шнур"]),
        ("grain_bait",       ["зернові", "горох кукурудза", "насадочні зернові", "кукуруза горох"]),
        ("boilie",           ["бойли"]),
        ("pop_up_bait",      ["поп ап", "поп-ап", "попап", "pop-up", "pop up", "поп ап бойл"]),
        ("pellets",          ["пелетс", "пелетси", "гранула", "мікс пелетсу", "парена гранула"]),
        ("bait_mix",         ["мікс пелетсу", "стік", "мікс стік", "готові пва стіки", "пва стіки"]),
        ("pva_material",     ["пва матеріали", "пва матеріал"]),
        ("liquid_attractant",["ліквіди", "ліквід", "ароматизатор", "дип", "спрей", "csl", "stick sauce", "меляса", "діп"]),
        ("groundbait",       ["прикормка", "прикорм", "кекс", "fshing mix", "fishing mix"]),
        ("foam_paste",       ["пінотісто макуха планктон", "пінотісто", "технопланктон", "макуха", "пластилін"]),
        ("float",            ["поплавки", "поплавок"]),
        ("jig_head",         ["головки", "джиг-головки", "джиг головки"]),
        ("feeder",           ["годівниц", "годівниці"]),
        ("weight",           ["вантажі", "вантаж"]),
        ("swivel",           ["вертлюги застібки", "вертлюг"]),
        ("ready_rig",        ["готові монтажі", "готовий монтаж", "готові оснастки"]),
        ("rigging",          ["все для монтажу оснащення", "все для монтажу", "оснащення монтаж | оснащення"]),
        ("landing_net",      ["підсаки"]),
        ("keepnet",           ["садки"]),
        ("nod",              ["кивки", "кивок"]),
        ("rod_rest_accessory",["аксесуари для підставки", "підставки", "rod-pod", "rod pod", "бузбар", "гребінки", "триноги"]),
        ("bite_indicator",   ["сигналізатори", "свінгер", "механічні сигналізатори"]),
        ("tools",            ["інструменти", "льодоруби", "льодобур", "сани ящики", "сушарки", "ліхтарі", "спомб", "ножиці", "батарейки"]),
        ("rod_tube",         ["чохли та тубоси", "тубус", "чохли"]),
        ("chair",            ["стільці"]),
        ("clothing",         ["рукавиці та носки", "взуття", "верхній одяг", "термобілизна", "окуляри", "головні убори"]),
        ("tackle_box",       ["ящики та коробки", "ящик"]),
        ("bag",              ["сумки", "поводочниці", "сумки та чохли"]),
        ("gift_certificate", ["сертифікати"]),
        ("camping_fuel",     ["газове обладнання"]),
        ("battery",          ["батарейки"]),
        ("flashlight",       ["ліхтарі"]),
    ]
    # Найглибший сегмент шляху — найточніший сигнал: "Спінінги і вудки /
    # Вудилища махові" має класифікуватись за "Вудилища махові", а не за
    # словом "спінінг" у батьківській папці.
    leaf = normalize_spaces((category_path or [""])[-1]).lower()
    if leaf:
        for family, cat_kws in cat_checks:
            if any(kw in leaf for kw in cat_kws):
                return family
    for family, cat_kws in cat_checks:
        if any(kw in cats for kw in cat_kws):
            return family

    # Якщо категорія не допомогла — шукаємо в назві
    name_checks = [
        ("reel",             ["катушка", "котушка"]),
        ("wobbler",          ["воблер", "wobbler"]),
        ("spinner",          ["блесн", "mepps"]),
        ("balancer",         ["балансир"]),
        ("jig_winter",       ["мормишка", "мармишка"]),
        ("hook",             ["офсетн", "трійник", "двійник", "гачок", "крючок"]),
        ("spinning",         ["спінінг"]),
        ("foam_paste",       ["тісто", "пінотісто", "макуха", "пластилін", "технопланктон", "глютен"]),
        # НЕ класифікуємо за брендом "Herabunafishing" — під ним і вудки, і
        # аксесуари (мотовила, ножиці, наконечники); сім'ю визначає категорія
        ("shock_leader",     ["шоклідер", "shock leader"]),
        ("fluorocarbon",     ["флюрокарбон"]),
        ("ready_leader",     ["повідець", "поводок"]),
        ("line",             ["волосінь", "ліска", "шнур"]),
        ("grain_bait",       ["кукуруза", "кукурудза", "горіх", "corn"]),
        ("boilie",           ["бойл", "boilie"]),
        ("pop_up_bait",      ["поп ап", "попап", "pop-up", "pop up", "popup"]),
        ("pellets",          ["пелетс", "pellets", "гранула"]),
        ("liquid_attractant",["ліквід", "liquid", "меляса", "спрей", "csl"]),
        ("feeder",           ["годівниц", "кормушк"]),
        ("float",            ["поплавок"]),
        ("weight",           ["вантаж", "грузило", "арлекін"]),
        ("swivel",           ["вертлюг", "застібк"]),
        ("ready_rig",        ["карповий монтаж", "готовий монтаж"]),
        ("pva_material",     ["пва сітка", "пва мішечок", "pva"]),
        ("groundbait",       ["прикормк", "прикорм"]),
        ("foam_paste",       ["пінотісто", "макуха", "пластилін", "технопланктон"]),
        ("landing_net",      ["підсак"]),
        ("keepnet",           ["садок"]),
        ("nod",              ["кивок"]),
        ("bite_indicator",   ["сигналізатор", "свінгер", "дзвіночок", "світлячок"]),
        ("tools",            ["плоскогубці", "ножиці", "дистанційна", "ехолот", "льодоруб", "льодобур"]),
        ("rod_tube",         ["тубус", "чохол для вудилища"]),
        ("chair",            ["стілець", "крісло", "карпове кресло"]),
        ("clothing",         ["дощовик", "рукавиці", "термошкарпетки", "куртка риболов", "костюм риболов"]),
        ("tackle_box",       ["ящик для снастей", "коробка для снастей"]),
        ("bag",              ["сумка риболов", "поводочниця"]),
        ("gift_certificate", ["сертифікат", "сертифкат"]),
        ("camping_fuel",     ["вугілля"]),
        ("battery",          ["крона", "батарейка"]),
        ("flashlight",       ["ліхтар", "ліхтарик"]),
    ]
    for family, text_kws in name_checks:
        if any(kw in text for kw in text_kws):
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

    cleaned = normalize_spaces(cleaned).strip(" -")
    lowered = cleaned.lower()

    leading_generic_by_family = {
        "line": ["шнур ", "ліска ", "волосінь "],
        "fluorocarbon": ["флюрокарбон ", "ліска ", "волосінь "],
        "shock_leader": ["шок-лідер ", "шоклідер "],
        "ready_leader": ["повідець ", "поводок "],
        "float": ["поплавок ", "поплавець "],
        "pva_material": ["пва матеріал ", "пва система ", "пва ", "pva "],
        "feeder": ["годівниця ", "годівниці "],
        "hook": ["гачок ", "крючок ", "офсетник "],
        "float_rod": ["вудка ", "вудочка ", "вудилище ", "удилище ", "карпове вудлище ", "фідер ", "пікер "],
        "foam_paste": ["тісто ", "пінотісто ", "макуха ", "пластилін "],
        "tackle_box": ["коробка ", "ящик ", "органайзер "],
        "bag": ["сумка ", "рюкзак ", "мішок "],
        "rod_tube": ["тубос ", "тубус ", "чохол ", "чехол "],
    }
    for prefix in leading_generic_by_family.get(family, []):
        if lowered.startswith(prefix):
            cleaned = normalize_spaces(cleaned[len(prefix):]).strip(" -")
            lowered = cleaned.lower()
            break

    if family == "spinning":
        while True:
            parts0 = cleaned.split()
            if not parts0:
                break
            head = parts0[0].lower()
            if head not in GENERIC_LEADING_TOKENS:
                break
            cleaned = normalize_spaces(" ".join(parts0[1:])).strip(" -")
        lowered = cleaned.lower()
        for brand_phrase in sorted(KNOWN_MULTIWORD_BRANDS, key=len, reverse=True):
            if lowered.startswith(brand_phrase + " "):
                words = cleaned.split()
                brand_words = brand_phrase.split()
                brand = " ".join(words[: len(brand_words)])
                model = " ".join(words[len(brand_words):])
                return normalize_spaces(brand), normalize_spaces(model)

    if family in {"line", "fluorocarbon", "shock_leader", "ready_leader", "float", "pva_material", "feeder", "float_rod"}:
        for brand_phrase in sorted(KNOWN_MULTIWORD_BRANDS, key=len, reverse=True):
            if lowered.startswith(brand_phrase + " "):
                words = cleaned.split()
                brand_words = brand_phrase.split()
                brand = " ".join(words[: len(brand_words)])
                model = " ".join(words[len(brand_words):])
                return normalize_spaces(brand), normalize_spaces(model)

    if family == "hook":
        cleaned = normalize_spaces(re.sub(r"^(?:№|#)?\s*[A-Za-zА-Яа-я0-9./\\+-]+\s+", "", cleaned)).strip(" -")
        lowered = cleaned.lower()

    parts = cleaned.split()
    if not parts:
        return "", ""

    if family in {"line", "fluorocarbon", "shock_leader", "float", "pva_material", "feeder", "hook", "tackle_box", "bag", "rod_tube"}:
        first = parts[0]
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9.+#/-]*", first):
            brand = first
            model = " ".join(parts[1:])
            return normalize_spaces(brand), normalize_spaces(model)

    if family == "ready_leader" and parts:
        first = parts[0]
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9.+#/-]*", first):
            brand = first
            model = " ".join(parts[1:])
            return normalize_spaces(brand), normalize_spaces(model)

    if family == "float_rod" and len(parts) > 1 and re.fullmatch(r"[A-Za-z][A-Za-z\s-]+", parts[-1]):
        brand = parts[-1]
        model = " ".join(parts[:-1])
        return normalize_spaces(brand), normalize_spaces(model)

    if family == "foam_paste" and len(parts) > 1 and re.fullmatch(r"[A-Za-z][A-Za-z0-9.+#/-]*", parts[-1]):
        brand = parts[-1]
        model = " ".join(parts[:-1])
        return normalize_spaces(brand), normalize_spaces(model)

    if family == "float_rod" and parts:
        first = parts[0]
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9.+#/-]*", first):
            brand = first
            model = " ".join(parts[1:])
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
    cats = " | ".join(category_path).lower()
    family = detect_family(name, category_path)
    type_word = FAMILY_LABELS.get(family, "Рибальський товар")
    base_name = name
    delta: dict[str, str] = {}
    common = dict(DEFAULT_COMMON_PARAMS.get(family, {}))
    if family == "foam_paste" and re.search(r"\bтісто\b|\bpaste\b", name, re.IGNORECASE):
        type_word = "Тісто"
        common["Тип насадки"] = "Тісто"
        common["Форма"] = "Паста / тісто"

    test_match, base_name = extract_token(TEST_RANGE_RE, base_name)
    test_min = test_max = None
    if test_match:
        tmin = parse_float(test_match.group(1))
        tmax = parse_float(test_match.group(2))
        if tmin is not None and tmax is not None and tmax >= tmin:
            test_min, test_max = tmin, tmax

    action_match = None
    action_num_match = None
    action = None
    if family in {"spinning", "float_rod"}:
        action_match, base_name = extract_token(ACTION_WORD_RE, base_name)
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
        val = parse_float(length_m_match.group(1))
        # Ігноруємо нереальні значення: вудилища 0.5–15м, лідери/повідці до 50м
        if val is not None and val <= (50 if family in {"ready_leader", "shock_leader", "line"} else 15):
            length_m = val
    else:
        length_cm_match, base_name = extract_token(LENGTH_CM_RE, base_name)
        # Воблери, силікон, балансири — довжина в см (не переводимо в метри)
        if length_cm_match and family in {"ready_leader", "bite_indicator", "wobbler", "silicone_lure", "balancer", "jig_winter", "spinner"}:
            add_param(delta, "Довжина", parse_float(length_cm_match.group(1)), " см")
        elif length_cm_match:
            value = parse_float(length_cm_match.group(1))
            if value is not None:
                length_m = round(value / 100, 2)

    diameter_match, base_name = extract_token(DIAMETER_MM_RE, base_name)
    if diameter_match:
        add_param(delta, "Діаметр", parse_float(diameter_match.group(1)), " мм")

    # Об'єм в мл — тільки для приманок/рідин, не для вудилищ/котушок/приманок
    _no_volume_families = {"spinning", "float_rod", "reel", "wobbler", "spinner",
                           "silicone_lure", "jig_head", "balancer", "jig_winter",
                           "hook", "nod", "bite_indicator", "rod_rest_accessory",
                           "ready_leader", "shock_leader", "fluorocarbon", "line"}
    if family not in _no_volume_families:
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

    item_count_match, base_name = extract_token(ITEM_COUNT_RE, base_name)
    if item_count_match:
        add_param(delta, "Комплектація", int(item_count_match.group(1)), " предмети")

    sections_match, base_name = extract_token(SECTIONS_RE, base_name)
    if sections_match:
        add_param(delta, "Кількість секцій", int(sections_match.group(1)), " секції")

    volt_match, base_name = extract_token(VOLT_RE, base_name)
    if volt_match:
        add_param(delta, "Напруга", parse_float(volt_match.group(1)), " V")

    battery_format_match, base_name = extract_token(BATTERY_FORMAT_RE, base_name)
    if battery_format_match:
        add_param(delta, "Форм-фактор", battery_format_match.group(1).upper())

    uah_amount_match, base_name = extract_token(UAH_AMOUNT_RE, base_name)
    if uah_amount_match:
        add_param(delta, "Номінал", parse_float(uah_amount_match.group(1)), " грн")

    # Гачок/розмір: №8, 2/0, 1\0
    hook_match, base_name = extract_token(HOOK_SIZE_RE, base_name)
    if hook_match:
        add_param(delta, "Розмір", hook_match.group(1))
    elif "Розмір" not in delta:
        slash_match, base_name = extract_token(HOOK_SLASH_RE, base_name)
        if slash_match:
            add_param(delta, "Розмір", f"{slash_match.group(1)}/{slash_match.group(2)}")

    dim_match, base_name = extract_token(DIMENSION_RE, base_name)
    if dim_match:
        add_param(delta, "Діаметр", parse_float(dim_match.group(1)), " мм")
        add_param(delta, "Довжина", parse_float(dim_match.group(2)), " мм")

    if family in {"bag", "tackle_box", "chair", "rod_tube"} and "Розмір" not in delta:
        any_dim_match, base_name = extract_token(DIMENSION_ANY_RE, base_name)
        if any_dim_match:
            parts = [parse_float(part) for part in any_dim_match.groups() if part]
            if len(parts) >= 2 and all(part is not None for part in parts):
                delta["Розмір"] = "x".join(f"{part:g}" for part in parts) + " см"

    # Дюйми (силіконові приманки)
    if family in {"silicone_lure", "other"} and "Розмір" not in delta:
        inch_match, base_name = extract_token(INCH_SIZE_RE, base_name)
        if inch_match:
            add_param(delta, "Розмір", parse_float(inch_match.group(1)), '"')

    # Об'єм у літрах (відра, термоси)
    if "Об'єм" not in delta:
        vol_l_match, base_name = extract_token(VOLUME_L_RE, base_name)
        if vol_l_match:
            add_param(delta, "Об'єм", parse_float(vol_l_match.group(1)), " л")

    # Літерний розмір (S/M/L/XL)
    if "Розмір" not in delta:
        size_m = SIZE_LETTER_RE.search(base_name)
        if size_m:
            add_param(delta, "Розмір", size_m.group(1))
        elif re.search(r"\bmedium\b", base_name, re.IGNORECASE):
            add_param(delta, "Розмір", "M")
        elif re.search(r"\blarge\b", base_name, re.IGNORECASE):
            add_param(delta, "Розмір", "L")
        elif re.search(r"\bsmall\b", base_name, re.IGNORECASE):
            add_param(delta, "Розмір", "S")

    if length_m is not None:
        add_param(delta, "Довжина", length_m, " м")
    if test_min is not None and test_max is not None:
        # Для воблерів test_range — це глибина занурення, не кастинговий тест
        if family in {"wobbler"}:
            delta["Глибина занурення"] = f"{test_min:g}-{test_max:g} м"
        elif family == "pva_material":
            delta["Розмір"] = f"{test_min:g}-{test_max:g} мм"
        else:
            delta["Тест"] = f"{test_min:g}-{test_max:g}"
    if action:
        delta["Стрій"] = action

    # Прибираємо prefix type_word з base_name щоб уникнути задвоєння ("Спінінг Спінінг X")
    _tw_lower = type_word.lower()
    _bn_lower = normalize_spaces(base_name).lower()
    if _bn_lower.startswith(_tw_lower + " ") or _bn_lower == _tw_lower:
        base_name = normalize_spaces(base_name[len(type_word):])
    # Також прибираємо поширені синоніми-префікси (рос. назви)
    _STRIP_PREFIXES = {
        "hook": ["крючок ", "крюк "],
        "reel": ["катушка ", "катушки "],
        "jig_winter": ["мормишка ", "мармишка "],
        "float_rod": ["удочка ", "вудочка "],
        "wobbler": ["воблер "],
        "spinner": ["блесна "],
    }
    for pfx in _STRIP_PREFIXES.get(family, []):
        if _bn_lower.startswith(pfx):
            base_name = normalize_spaces(base_name[len(pfx):])
            break

    brand, model_name = family_brand_model(family, base_name)
    if not brand and family in {"grain_bait", "boilie", "pop_up_bait", "pellets", "bait_mix", "liquid_attractant"}:
        quoted = QUOTED_BRAND_RE.findall(name)
        if quoted:
            brand = quoted[-1]

    cleaned_for_flavor = normalize_spaces(base_name.replace(brand, "", 1) if brand else base_name)
    display_name = normalize_spaces(" ".join(part for part in [type_word, brand, model_name] if part))

    if family in {"grain_bait", "boilie", "pop_up_bait", "pellets", "bait_mix", "liquid_attractant"}:
        flavor_candidate = cleaned_for_flavor
        for marker in ["Тигровий Горіх", "Кукуруза Цукрова", "Кукурудза Цукрова", "Бойли", "Поп ап", "Поп-ап",
                        "Пелетс", "Гранула", "Мікс", "Стік", "Ліквід", "Пінотісто", "Макуха"]:
            flavor_candidate = flavor_candidate.replace(marker, "").strip(" -")
        if flavor_candidate and len(flavor_candidate.split()) <= 5:
            common["Аромат"] = flavor_candidate

    lowered = name.lower()

    if family == "line":
        if BRAID_RE.search(name):
            common["Тип"] = "Плетений шнур"
        if "фідер" in lowered:   common["Призначення"] = "Фідерна риболовля"
        if "карп" in lowered:    common["Призначення"] = "Коропова риболовля"
        if "зима" in lowered:    common["Призначення"] = "Зимова риболовля"
        if "спрей" in lowered or "силікон" in lowered:
            common["Тип"] = "Догляд за волосінню / шнуром"
            common["Призначення"] = "Обробка шнурів і волосіні"
    if family == "fluorocarbon":
        common["Матеріал"] = "Флюрокарбон"
    if family == "shock_leader":
        common["Тип"] = "Шок-лідер"
    if family == "ready_leader":
        if "карпов" in lowered:       common["Призначення"] = "Карпова риболовля"
        if "флюрокарбон" in lowered:  common["Матеріал"] = "Флюрокарбон"
        if "wolfram" in lowered or "вольфрам" in lowered: common["Матеріал"] = "Вольфрам"
        if "титан" in lowered:        common["Матеріал"] = "Титан"
    if family == "nod":
        if "лавсан" in lowered:       common["Матеріал"] = "Лавсан"
        if "зима" in lowered:         common["Призначення"] = "Зимова риболовля"
    if family == "bite_indicator":
        if "світлячок" in lowered:    common["Підтип"] = "Під світлячок"
        elif "свінгер" in lowered:    common["Підтип"] = "Свінгер"
        elif "дзвіночок" in lowered:  common["Підтип"] = "Дзвіночок"
        elif "механіч" in lowered:    common["Підтип"] = "Механічний"
        elif "електрон" in lowered:   common["Підтип"] = "Електронний"

    # ── Котушки ────────────────────────────────────────────────────────
    if family == "reel":
        reel_m = REEL_SIZE_RE.search(name)
        if reel_m:
            add_param(delta, "Розмір", reel_m.group(1))
        bear_m = BEARING_RE.search(name)
        if bear_m:
            add_param(delta, "Підшипники", int(bear_m.group(1)) + 1, " шт")
        if "карп" in lowered:    common["Тип"] = "Карпова котушка"
        elif "фідер" in lowered: common["Тип"] = "Фідерна котушка"
        elif "зима" in lowered:  common["Тип"] = "Зимова котушка"
        elif "інерц" in lowered: common["Тип"] = "Інерційна котушка"
        else:                    common["Тип"] = "Безінерційна котушка"

    # ── Гачки ──────────────────────────────────────────────────────────
    if family == "hook":
        if "офсет" in lowered:    common["Тип"] = "Офсетний"
        elif "трійник" in lowered: common["Тип"] = "Трійник"
        elif "двійник" in lowered: common["Тип"] = "Двійник"
        elif "одинарн" in lowered: common["Тип"] = "Одинарний"
        else:                      common["Тип"] = "Одинарний"
        if "вольфрам" in lowered:  common["Матеріал"] = "Вольфрам"
        elif "карбон" in lowered:  common["Матеріал"] = "Сталь"
        else:                      common.setdefault("Матеріал", "Сталь")

    # ── PVA матеріали ──────────────────────────────────────────────────
    if family == "pva_material":
        common["Матеріал"] = "PVA"
        common["Призначення"] = "Коропова риболовля"
        if "сітка" in lowered:
            common["Тип"] = "PVA сітка"
        elif "нитк" in lowered or "мотузк" in lowered:
            common["Тип"] = "PVA нитка"
        elif "пакет" in lowered or "мішеч" in lowered:
            common["Тип"] = "PVA пакет"
        elif "система" in lowered:
            common["Тип"] = "PVA система"
        elif "тубос" in lowered or "тубус" in lowered:
            common["Тип"] = "Тубус для PVA"
        elif "клей" in lowered or "гель" in lowered or "фіксатор" in lowered:
            common["Тип"] = "Допоміжний PVA аксесуар"
        if "гель" in lowered:
            common["Форма випуску"] = "Гель"
        elif "клей" in lowered:
            common["Форма випуску"] = "Клей"
        if "тепла вода" in lowered:
            common["Умови використання"] = "Тепла вода"
        elif "холодна вода" in lowered:
            common["Умови використання"] = "Холодна вода"

    # ── Грузила / монтажні ваги ───────────────────────────────────────
    if family == "weight":
        if "вухань" in lowered:
            common["Форма грузила"] = "Вухань"
        elif "дроп шот" in lowered:
            common["Форма грузила"] = "Дроп-шот"
        elif "банан" in lowered:
            common["Форма грузила"] = "Банан"
        elif "ромб" in lowered:
            common["Форма грузила"] = "Ромб"
        elif "шар" in lowered or "куля" in lowered:
            common["Форма грузила"] = "Куля"
        elif "голова риби" in lowered:
            common["Форма грузила"] = "Голова риби"
        elif "дробин" in lowered:
            common["Форма грузила"] = "Дробинка"
        common.setdefault("Матеріал", "Свинець")

    # ── Інструменти ────────────────────────────────────────────────────
    if family == "tools":
        common["Призначення"] = "Монтаж оснастки"
        if "голка" in lowered:
            common["Тип"] = "Голка монтажна"
        elif "ножиц" in lowered:
            common["Тип"] = "Ножиці"
        elif "рогатк" in lowered:
            common["Тип"] = "Рогатка"
        elif "свердл" in lowered:
            common["Тип"] = "Свердло"
        elif "шило" in lowered:
            common["Тип"] = "Шило"
        elif "петлевяз" in lowered:
            common["Тип"] = "Петлев'яз"
        elif "пучковяз" in lowered:
            common["Тип"] = "Пучков'яз"
        elif "ніж" in lowered and ("льодоруб" in lowered or "льодобур" in lowered):
            common["Тип"] = "Ножі для льодобура"
            common["Сезон"] = "Зимова риболовля"
        elif "льодоруб" in lowered or "льодобур" in lowered or "бур " in lowered:
            common["Тип"] = "Льодобур"
            common["Сезон"] = "Зимова риболовля"
        elif "ліхтар" in lowered:
            common["Тип"] = "Ліхтар"
            common["Призначення"] = "Освітлення"
        elif "крона" in lowered or "батарейк" in lowered:
            common["Тип"] = "Батарейка"
            common["Призначення"] = "Живлення аксесуарів"
        if "метал" in lowered:
            common["Матеріал"] = "Метал"
        elif "пластик" in lowered:
            common["Матеріал"] = "Пластик"
        if "набір" in lowered and "Комплектація" not in delta:
            common["Комплектація"] = "Набір інструментів"
        elif "свердл" in lowered and "шило" in lowered and "Комплектація" not in delta:
            common["Комплектація"] = "Шило та свердло"
        if "під шурупокрут" in lowered or "шурупокрут" in lowered:
            common["Сумісність"] = "Під шурупокрут"

    if family == "groundbait":
        common["Тип"] = "Прикормка"
        common["Консистенція"] = "Суха"
        if "flat feeder" in lowered or "фідер" in lowered:
            common["Призначення"] = "Фідерна риболовля"
        elif "короп" in lowered:
            common["Призначення"] = "Коропова риболовля"
        elif "карась" in lowered:
            common["Призначення"] = "Ловля карася"

    if family == "swivel":
        common["Матеріал"] = "Метал"
        if "застібк" in lowered:
            common["Тип"] = "Застібка"
        elif "вертлюг" in lowered:
            common["Тип"] = "Вертлюг"
        if "фідер" in lowered:
            common["Призначення"] = "Фідерний монтаж"

    if family == "float":
        common["Тип"] = "Поплавок"
        common["Призначення"] = "Поплавкова ловля"
        common["Вид"] = "Класичний"
        if "батарейк" in lowered:
            common["Тип"] = "Батарейка для поплавка"
        if "херабуна" in cats:
            common["Вид"] = "Херабуна"

    if family == "keepnet":
        common["Тип"] = "Садок"
        common["Призначення"] = "Зберігання риби"
        if "кругл" in lowered:
            common["Форма"] = "Круглий"
        elif "прям" in lowered:
            common["Форма"] = "Прямокутний"

    if family == "landing_net":
        if "ручка" in lowered:
            common["Тип"] = "Ручка для підсака"
        else:
            common["Тип"] = "Підсак"
        common["Призначення"] = "Виважування риби"
        if "телескоп" in lowered or re.search(r"\blf\d+", lowered):
            common["Конструкція"] = "Телескопічна / складна"

    if family == "rod_tube":
        if "тубус" in lowered:
            common["Тип"] = "Тубус"
        else:
            common["Тип"] = "Чохол"
        common["Призначення"] = "Транспортування снастей"
        if "жорстк" in lowered:
            common["Конструкція"] = "Жорстка"
        elif "чехол" in lowered or "чохол" in lowered:
            common["Конструкція"] = "М'яка"
        if "блеш" in lowered or "мормиш" in lowered:
            common["Підходить для"] = "Блешні та мормишки"
        elif "вудилищ" in lowered:
            common["Підходить для"] = "Вудилища"

    if family == "ready_rig":
        common["Тип"] = "Готовий монтаж"
        if "карася" in lowered:
            common["Призначення"] = "Ловля карася"
            common["Вид монтажу"] = "Вбивця карася"
        elif "товстолоб" in lowered or "толстолоб" in lowered:
            common["Призначення"] = "Ловля товстолоба"
            common["Вид монтажу"] = "На товстолоба"
        elif "фідер" in lowered:
            common["Призначення"] = "Фідерна риболовля"
            common["Вид монтажу"] = "Фідерний"
        if "банан" in lowered:
            common["Форма грузила"] = "Банан"
        elif "пуля" in lowered:
            common["Форма грузила"] = "Пуля"

    if family == "feeder":
        common["Тип"] = "Годівниця"
        common["Призначення"] = "Фідерна риболовля"
        common["Матеріал"] = "Метал"
        if "метод" in lowered:
            common["Підтип"] = "Метод"
        elif "ложка" in lowered:
            common["Підтип"] = "Ложка"
        else:
            common["Підтип"] = "Клітка"

    if family == "chair":
        common["Призначення"] = "Риболовля та кемпінг"
        if "крісло" in lowered:
            common["Тип"] = "Крісло"
        else:
            common["Тип"] = "Стілець"
        if "полиц" in lowered:
            common["Особливість"] = "З полицею"
        if "м'як" in lowered or "мяк" in lowered:
            common["Комфорт"] = "М'яке сидіння"

    if family == "tackle_box":
        common["Призначення"] = "Зберігання снастей"
        if "ящик" in lowered:
            common["Тип"] = "Ящик для снастей"
        else:
            common["Тип"] = "Коробка для снастей"
        if "короб" in lowered and "Кількість відділень" not in delta:
            box_count = re.search(r"(\d+)\s*короб", lowered)
            if box_count:
                add_param(delta, "Комплектація", box_count.group(1), " коробки")

    if family == "bag":
        if "повідочниц" in lowered or "поводочниц" in lowered:
            common["Тип"] = "Повідочниця"
            common["Призначення"] = "Зберігання повідців"
        elif "термосум" in lowered:
            common["Тип"] = "Термосумка"
            common["Призначення"] = "Зберігання наживки та продуктів"
        else:
            common["Тип"] = "Сумка рибальська"

    if family == "foam_paste":
        if "макуха" in lowered:
            common["Тип"] = "Макуха"
        elif "пластилін" in lowered:
            common["Тип"] = "Рибальський пластилін"
        elif "пінотісто" in lowered:
            common["Тип"] = "Пінотісто"
        elif "тісто" in lowered:
            common["Тип"] = "Тісто"
        variant = normalize_spaces(
            re.sub(
                r"\b(?:тісто|пінотісто|макуха|пластилін|herabunafishing)\b",
                " ",
                base_name,
                flags=re.IGNORECASE,
            )
        ).strip(" -")
        if variant:
            common["Аромат/варіант"] = variant

    if family == "rigging":
        common["Тип"] = "Монтажна оснастка"
        if "стопор" in lowered:
            common["Підтип"] = "Стопор"
        elif "силікон" in lowered or "кембрик" in lowered:
            common["Підтип"] = "Силіконова оснастка"
            common["Матеріал"] = "Силікон"
        elif "коромисло" in lowered:
            common["Підтип"] = "Коромисло"
        if "горох" in lowered:
            common["Призначення"] = "Насадка під горох"

    if family == "gift_certificate":
        common["Тип"] = "Подарунковий сертифікат"
        common["Призначення"] = "Подарунок рибалці"

    if family == "camping_fuel":
        common["Тип"] = "Вугілля"
        common["Призначення"] = "Кемпінг і приготування їжі"
        common["Форма випуску"] = "Деревне вугілля"

    if family == "battery":
        common["Тип"] = "Батарейка"
        if "крона" in lowered:
            common["Підтип"] = "Крона"

    if family == "flashlight":
        common["Тип"] = "Ліхтар"
        common["Призначення"] = "Освітлення"
        common["Джерело живлення"] = "Батарейки"

    # ── Воблери ────────────────────────────────────────────────────────
    if family == "wobbler":
        if "floating" in lowered or "плаваюч" in lowered:
            common["Плавучість"] = "Плаваючий"
        elif "sinking" in lowered or "тонучий" in lowered or "tonuch" in lowered:
            common["Плавучість"] = "Тонучий"
        elif "suspend" in lowered:
            common["Плавучість"] = "Суспендер"

    # ── Блешні / приманки ──────────────────────────────────────────────
    if family == "spinner":
        if "колебалк" in lowered or "колівалка" in lowered or "кастмастер" in lowered:
            common["Тип"] = "Коливалка"
        elif "вертушк" in lowered or "mepps" in lowered:
            common["Тип"] = "Вертушка"
        elif "тел-спіннер" in lowered:
            common["Тип"] = "Тел-спіннер"

    # ── Мормишки ───────────────────────────────────────────────────────
    if family == "jig_winter":
        if TUNGSTEN_RE.search(name):
            common["Матеріал"] = "Вольфрам"
        else:
            common["Матеріал"] = "Свинець"
        if "кулька" in lowered:   common["Форма"] = "Кулька"
        elif "крапля" in lowered: common["Форма"] = "Крапля"
        elif "муравей" in lowered or "мурашка" in lowered: common["Форма"] = "Мурашка"

    # ── Балансири ──────────────────────────────────────────────────────
    if family == "balancer":
        common["Призначення"] = "Зимова риболовля"

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
