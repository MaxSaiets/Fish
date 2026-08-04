from __future__ import annotations

import html
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape
import re

from catalog_rules import parse_product
from feed_content import build_variant_title, resolve_description_html
from horoshop_reset_seed_structure import PRODUCTS_JSON, SKIP_NAMES, STRUCTURE, map_product_to_target_path

ROOT = Path(__file__).resolve().parent.parent
META_DB = ROOT / "data" / "meta_store.sqlite"
OUT_XML = ROOT / "public" / "horoshop.xml"
OVERRIDES_JSON = ROOT / "data" / "horoshop_overrides.json"

FIXED_XLS_COLUMNS = [
    "Артикул",
    "Назва",
    "Розділ",
    "Ціна",
    "Валюта",
    "Відображати на сайті",
    "Наявність",
    "Бренд",
    "Шаблон даних",
    "Кількість",
    "Опис товару",
]

PARAM_PRIORITY = [
    "Тип вудилища",
    "Тип насадки",
    "Тип суміші",
    "Тип атрактанту",
    "Тип",
    "Підтип",
    "Форма",
    "Матеріал",
    "Плавучість",
    "Довжина",
    "Тест",
    "Стрій",
    "Діаметр",
    "PE",
    "Розривне навантаження",
    "Розривне навантаження (lb)",
    "Об'єм",
    "Вага",
    "Розмір",
    "Підшипники",
    "Кількість в упаковці",
    "Призначення",
    "Аромат",
    "Кастинг-тест",
    "Лад",
    "Глибина занурення",
]

NOT_A_BRAND = {
    "вудочка",
    "вудка",
    "вудилище",
    "удилище",
    "спінінг",
    "фідер",
    "котушка",
    "шнур",
    "шнури",
    "ліска",
    "волосінь",
    "флюорокарбон",
    "флюрокарбон",
    "силікон",
    "силіконова",
    "мормишка",
    "балансир",
    "блешня",
    "воблер",
    "гачок",
    "крючок",
    "годівниця",
    "поплавок",
    "прикормка",
    "бойл",
    "пелетс",
    "зернові",
    "повідець",
    "мотовило",
    "набір",
    "конектор",
    "запасне",
    "карпове",
    "штек",
    "штек.",
    "штекер",
    "штекер.",
}

INVALID_XML_CHARS = dict.fromkeys(list(range(0, 9)) + [11, 12] + list(range(14, 32)), None)

BRAND_ALIASES: list[tuple[str, tuple[str, ...]]] = [
    ("Select", ("select", "seect")),
    ("JAXON", ("jaxon",)),
    ("Fanatik", ("fanatik", "фанатік")),
    ("3K BAITS", ("3-k baits", "3k baits", "3-к baits", "3 k baits")),
    ("Keitech", ("keitech",)),
    ("Flagman", ("flagman", "fagman", "flsgman")),
    ("MEPPS", ("mepps",)),
    ("Rapala", ("rapala",)),
    ("WIST", ("wist",)),
    ("RELAX", ("relax",)),
    ("REINS", ("reins",)),
    ("MISO-BAIT", ("miso-bait", "mico-bait")),
    ("Sabaroff", ("sabaroff",)),
    ("Kazara", ("казара", "kazara")),
    ("X-CROBS", ("x-crobs",)),
    ("GC", (" gc ", "g.carp", "g-carp", "golden catch", " gc-", "gc ", "gc")),
    ("RPF", ("rpf",)),
    ("FEIMA", ("feima", "afeima")),
    ("BOUNTY", ("bounty",)),
    ("Brain", ("brain",)),
    ("Intech", ("intech",)),
    ("Owner", ("owner",)),
    ("Kalipso", ("kalipso",)),
    ("Kaipso", ("kaipso",)),
    ("Siweida", ("siweida",)),
    ("WEIDA", ("weida",)),
    ("OSPREY", ("osprey",)),
    ("EOS", ("eos",)),
    ("Favorite", ("favorite", "favorit")),
    ("River Tramp", ("river tramp", "rivertramp")),
    ("Lucky John", ("lucky john",)),
    ("MISTRALL", ("mistrall",)),
    ("Hayabusa", ("hayabusa",)),
    ("Carp Pro", ("carp pro",)),
    ("Carp Fishing", ("carp fishing",)),
    ("Carp Expert", ("carp expert",)),
    ("Cetcher Expert", ("cetcher expert",)),
    ("GAMAKATSU", ("gamakatsu",)),
    ("KAMATSU", ("kamatsu", "kamalsu", "kamalsu aji", "kamalsu iseama")),
    ("KATANA", ("katana",)),
    ("Vido Craft", ("vido craft",)),
    ("LEADER", ("leader",)),
    ("Winner", ("winer", "winner", "winer shogun", "winner shogun")),
    ("Heranunafishing", ("heranunafishing",)),
    ("Maori Fish", ("maori fish",)),
    ("Master Hooks", ("master hooks",)),
    ("Akara", ("akara",)),
    ("ROBIN", ("robin", "elite robin", "robin sweet", "robin pop-ups")),
    ("Angel Sport", ("angel sport",)),
    ("Fishing Forever", ("fishing forever",)),
    ("UP-Coron", ("up-coron",)),
    ("UZH BAIT", ("uzh bait",)),
    ("Trinity Baits", ("trinity baits",)),
    ("Carp Catcher", ("carp catcher",)),
    ("Fishing Mix", ("fshing mix", "fishing mix")),
    ("Techno", ("techno",)),
    ("Fish Sport", ("fish sport",)),
    ("Karpusha", ("карпуша",)),
    ("PELORUS CARP", ("pelorus carp",)),
    ("KORONA", ("корона",)),
    ("L.E.", ("l. e.", "l.e.")),
    ("Grizzly", ("grizzly",)),
    ("Art Fishing", ("art fishing",)),
    ("Carp Zoom", ("carp zoom",)),
    ("ANVI FISHING", ("anvi fishing",)),
    ("INTERKRIL", ("interkrill", "interkril")),
    ("RealFish", ("realfish", "real fish")),
    ("Apache", ("apache",)),
    ("Shark", ("shark",)),
    ("Rumpol", ("rumpol",)),
    ("MIFINE", ("mifine",)),
    ("Puhach Baits", ("puhach baits",)),
    ("DURALURE", ("duralure",)),
    ("Robinson", ("robinson",)),
    ("Mikado", ("mikado",)),
    ("Lemigo", ("lemigo",)),
    ("Stonfo", ("stonfo", "sonfo")),
    ("Azura", ("azura",)),
    ("Sams Fish", ("sams fish",)),
    ("Carp Line", ("carp line",)),
    ("Sky Fish", ("sky fish",)),
    ("DreamStan", ("dreamstan",)),
    ("Norfin", ("norfin", "norfin", "rfin")),
    ("Reis", ("reis",)),
    ("Viking Fishing", ("viking fishing",)),
    ("ProfMontazh", ("профмонтаж", "prof montazh", "profmontazh")),
    ("Techno Carp", ("techno carp", "technocarp", "texnoкарп")),
    ("Kumho", ("kumho",)),
    ("Kosadaka", ("kosadaka",)),
    ("Strike Pro", ("strikepro", "strike pro")),
    ("Cukk", ("cukk",)),
    ("Kamasaki", ("kamasaki",)),
    ("VIDEX", ("videx",)),
    ("SENSON", ("senson",)),
    ("TONAR", ("tonar",)),
    ("SPINNEX", ("spinnex",)),
    ("KASTMASTER", ("kastmaster",)),
    ("ACCURAT", ("accurat", "аккурат")),
    ("Duraking", ("duraking",)),
    ("PUFFI", ("puffi",)),
    ("STINGER", ("stinger",)),
    ("PHANTOM", ("phantom",)),
    ("VIBRAX", ("vibrax",)),
    ("XINGS HENGYUJU", ("xings hengyuju",)),
    ("REELS", ("reels",)),
    ("Kuusamo", ("kuusamo", "kusama")),
    ("VAST", ("vast",)),
    ("VIKING", ("viking", "viking ice pro")),
    ("Stubla", ("stubla", "стубла")),
    ("ECLIPSE", ("eclipse",)),
    ("ROY", ("roy",)),
    ("Lucky John", ("luky john",)),
    ("ELIT", ("elit",)),
    ("BEST", ("best",)),
    ("Hi Mera", ("hi mera",)),
    ("Ice Attack", ("ice attack",)),
    ("ORANGE", ("orange",)),
    ("GLOBE", ("globe",)),
    ("DRAGON", ("dragon",)),
    ("Power Pro", ("power pro",)),
    ("Ryobi", ("ryobi",)),
    ("AOQIUSITE", ("aoqiusite",)),
    ("BAICHENG", ("baicheng",)),
    ("BIG WASP", ("big wasp",)),
    ("Cobra", ("cobra", "cobla")),
    ("DURAREEL", ("durareel",)),
    ("CONDOR", ("condor",)),
    ("GERMAN", ("german",)),
    ("BRAT FISHING", ("brat fishing",)),
    ("ALEKSANDR LURE", ("aleksandr lure",)),
    ("GUAN MING", ("guan ming",)),
    ("Farther", ("farther",)),
    ("Fly", ("fly",)),
    ("HAIBAO FISHING", ("haibao fishing",)),
    ("Hiboy", ("hiboy",)),
    ("KANDO", ("kando",)),
    ("Legend Fishing Gear", ("legend fishing gear",)),
    ("MARLIN", ("marlin",)),
    ("TOPAZ", ("topaz",)),
    ("Viva Tactics", ("viva tactics",)),
    ("Orange Carp", ("orange carp",)),
    ("ORANGE", ("orang",)),
    ("Sunline", ("sunline", "sunline siglon pe", "sunline basic pe")),
    ("Dura King", ("dura king", "dura king natuna")),
    ("Kamatsu", ("kamatsu", "kamatsu swivels")),
    ("Big Fish", ("big fish", "big fish feeder")),
    ("LEGENDA", ("legenda", "legenda supers", "super strong legend")),
    ("Ukrspin", ("ukrspin", "ukrspin orange", "ukrspin orange spinning")),
    ("DIWA", ("diwa", "diwa pe jigger", "diwa avengers super")),
    ("YGK", ("ygk", "ygk x-braid", "ygk x-braid upgrade")),
    ("Daiwa", ("daiwa", "daiva", "daiwa j-braid", "daiwa j-braid expedition", "daiva j-braid")),
    ("Varivas", ("varivas", "varivas hight grade")),
    ("Carpzoom", ("carpzoom", "carpzoom cz method")),
    ("PHOENIX", ("phoenix",)),
    ("FOX", ("fox",)),
    ("BOYA BY CARP", ("boya by carp",)),
    ("XPS", ("xps", "xps soft touch")),
    ("ARCTIL", ("arctil",)),
    ("ICE KING", ("ice king",)),
    ("Konger", ("konger", "konger fishing expert", "konger steelon fluorocarbon", "steelon konger")),
    ("PREVIA", ("previa",)),
    ("FishHunter", ("fishhunter",)),
    ("BigCatch", ("bigcatch", "bigcetch")),
    ("SUFIX", ("sufix",)),
    ("Spirit", ("spirit nylon", "spirit")),
    ("KAIDA", ("kaida", "kaida max power")),
    ("Winner", ("winner king fisher", "winner")),
    ("TOUGHLON", ("toughlon", "toughlon stamina")),
    ("MILLENIUM", ("millenium", "millenium carp", "millenium zonben")),
    ("SALON", ("salon carp", "salon sum", "salon pike")),
    ("SILVER FISH", ("silver fish",)),
    ("CARP BLACK", ("carp black",)),
    ("HUNTERS", ("hunters kutbert",)),
    ("ICE FOX", ("ice fox",)),
    ("BASARA", ("basara",)),
    ("Gladiator", ("gladiator",)),
    ("Sapfir", ("sapfir",)),
    ("ZEOX", ("zeox", "zeox element leader")),
    ("STRATEGY", ("strategy", "strategy sp", "strategy sp x4")),
    ("POWER ZONE", ("power zone", "advantage power zone")),
    ("BOYA BY", ("boya by",)),
    ("FISHUNTER", ("fishunter", "fishhunter")),
    ("Golden Fish", ("golden fish",)),
    ("Okuma", ("okuma",)),
    ("Titan", ("titan",)),
    ("ZHIBO", ("zhibo",)),
    ("Guangwei", ("guangwei",)),
    ("Arrast", ("arrast",)),
    ("Nikoma", ("nikoma",)),
    ("Garbolino", ("garbolino",)),
    ("NEW HUNTER", ("new hunter",)),
    ("PANTHER", ("panther",)),
    ("Sport Night", ("sport niht", "sport night")),
    ("Superior", ("superior carp", "superior")),
    ("Temptation", ("temptation",)),
    ("Knight", ("knight",)),
    ("CATANA", ("catana",)),
    ("GENETIC", ("genetic",)),
    ("Sadei", ("sadei",)),
    ("MEGASTRIKE", ("megastrike",)),
    ("FOS", ("fos",)),
    ("Royal Fish", ("royal fish",)),
    ("OWNER", ("owner",)),
    ("Mustad", ("mustad",)),
    ("Meiho", ("meiho",)),
    ("Aquatech", ("aquatech",)),
    ("ECLIPS", ("eclips",)),
    ("KIBAS", ("kibas",)),
    ("Hirisi", ("hirisi",)),
    ("Renger", ("renger",)),
    ("FFC", ("ffc",)),
    ("ProfMontazh", ("проф монтаж", "профмонтаж", "prof montazh", "profmontazh")),
    ("PM", (" пм ",)),
    ("Fishing Box", ("fishing box",)),
    ("SOLARIS", ("solaris",)),
    ("Blino", ("blino",)),
    ("Breeze", ("breeze",)),
    ("Fishing ROI", ("fishing roi",)),
    ("Fishing Ro", ("fishing ro",)),
    ("X-Fish", ("x-fish", "x fish")),
    ("Mildaz", ("mildaz", "mildas", "мільдаз")),
    ("Craft Hook", ("craft hook",)),
    ("N-ICE", ("n-ice",)),
    ("Yeyingzhe", ("yeyingzhe",)),
    ("Catchers", ("catchers",)),
    ("Ranger", ("ranger",)),
    ("Stream", ("stream",)),
    ("Kang Lida", ("kang lida",)),
    ("Big Catch", ("big cath", "big catch")),
    ("Korsar", ("korsar",)),
    ("Brave", ("brave",)),
    ("Silver Carp", ("silver carp", "siver carp")),
    ("SENSOR", ("sensor",)),
    ("Carp Magellan", ("carp magellan",)),
    ("Skif Outdoor", ("skif outodor", "skif outdoor", "skif")),
    ("BULICK", ("bulick",)),
    ("KLD", ("kld",)),
    ("OOSHIMA", ("ooshima",)),
    ("Kyogi", ("kyogi",)),
    ("Marline", ("marline",)),
    ("BOYA", ("boyaby", "boya bu", "boya by")),
    ("Strong Wind", ("strong wind",)),
    ("Splendid", ("splendid",)),
    ("Eclipse", ("eclapse", "eclipse")),
]

SUSPICIOUS_NAME_PATTERNS = [
    re.compile(r"^(?:test|tetg|qwerty|asdf|my item|мій товар)$", re.IGNORECASE),
    re.compile(r"^(?:wterterwer|werwer|werterwer|asdfasdf|йцукен|фівапролдж)$", re.IGNORECASE),
    re.compile(r"^[\d.\-+/ ]{1,8}$"),
]

DROP_PARAMS_BY_FAMILY = {
    "spinning": {"PE", "Діаметр", "Розривне навантаження", "Розривне навантаження (lb)", "Застібка", "Кількість відділень"},
    # махові вудки без кілець/котушкотримача: "Тип пропускних кілець"/"Кількість
    # секцій"/"Транспортна довжина"/"Тип рукояті" — вигадки старого AI-генератора
    "float_rod": {"PE", "Діаметр", "Розмір", "Кількість в упаковці",
                  "Тип пропускних кілець", "Кількість секцій",
                  "Транспортна довжина", "Транспортна довжина (см)", "Тип рукояті"},
    "reel": {"Тип вудилища", "Матеріал бланка", "Кількість секцій", "Тип рукояті", "Тип пропускних кілець", "Транспортна довжина", "Транспортна довжина (см)", "Тест", "Кастинг-тест", "PE"},
    "hook": {"PE", "Тест", "Кастинг-тест", "Довжина", "Вага", "Тип хвоста", "Діаметр", "Розривне навантаження"},
    "feeder": {"Стрій", "Лад", "Діаметр", "Об'єм"},
    "weight": {"Тест", "Кастинг-тест", "Фарба", "Використання"},
    "swivel": {"PE", "Вага", "Діаметр", "Довжина", "Матеріал повідця", "Тип повідця", "Кількість відділень"},
    "groundbait": {"Матеріал", "Модель", "Вид", "Спосіб застосування", "Структура", "Діаметр"},
    "foam_paste": {"Матеріал бланка", "Кількість секцій", "Тип рукояті", "Тип пропускних кілець", "Тип з'єднання секцій", "Транспортна довжина", "Транспортна довжина (см)", "Кастинг-тест", "Стрій", "Лад"},
    "pellets": {"Тип вудилища", "Матеріал бланка", "Кількість секцій", "Транспортна довжина", "Тип пропускних кілець", "Тип рукояті", "Розривне навантаження"},
    "boilie": {"Тип монтажу", "Розривне навантаження", "Довжина", "Розмір гачка", "Кількість гачків", "Клас"},
    "pop_up_bait": {"Тип воблера", "Кількість гачків", "Сумісність"},
    "liquid_attractant": {"Тип насадки", "Плавучість"},
    "line": {"Тип приманки", "Плавучість", "Тип воблера", "Глибина занурення", "Матеріал бланка", "Кількість секцій", "Тип пропускних кілець", "Тип рукояті", "Тип вудилища", "Кількість полиць", "Місткість", "Колір підсвічування", "Транспортна довжина", "Довжина шнура", "Кількість застібок"},
    "fluorocarbon": {"Тип приманки", "Плавучість", "Тип воблера", "Глибина занурення"},
    "shock_leader": {"Тип приманки", "Плавучість", "Тип воблера", "Глибина занурення"},
    "ready_leader": {"Тип приманки", "Плавучість", "Тип воблера", "Глибина занурення", "Матеріал бланка", "Кількість секцій", "Транспортна довжина", "Тип пропускних кілець", "Тип рукояті", "Стрій", "Лад"},
    "wobbler": {"Матеріал бланка", "Кількість секцій", "Тип рукояті", "PE", "Кастинг-тест", "Напруга", "Діаметр"},
    "spinner": {"PE", "Тест", "Кастинг-тест", "Діаметр"},
    "balancer": {"PE", "Тест", "Кастинг-тест", "Діаметр"},
    "silicone_lure": {"PE", "Діаметр"},
    "rod_tube": {"Тест", "Кастинг-тест", "Кількість секцій", "Діаметр"},
    "chair": {"Діаметр", "Стрій", "Лад"},
    "tackle_box": {"PE", "Тест", "Кастинг-тест", "Кількість секцій", "Тип вудилища", "Матеріал бланка", "Тип рукояті", "Діаметр"},
    "bag": {"Стрій", "Лад", "Кількість секцій", "Тип вудилища", "Матеріал бланка", "Тип пропускних кілець", "Тип рукояті", "PE", "Кастинг-тест"},
    "clothing": {"PE", "Тест", "Кастинг-тест", "Діаметр", "Стрій", "Лад", "Тип вудилища", "Матеріал бланка", "Кількість секцій", "Транспортна довжина", "Тип пропускних кілець", "Тип рукояті"},
    "float": {"PE", "Тест", "Кастинг-тест", "Кількість відділень", "Упаковка", "Водопроникність", "Водонепроникність", "Живлення"},
    "keepnet": {"PE", "Кількість крючків", "Поплавки", "Об'єм", "Водонепроникність"},
    "landing_net": {"Тест", "Кастинг-тест", "Напруга", "Мережа", "Кількість секцій"},
    "bite_indicator": {"Тест", "Кастинг-тест", "Вага", "Довжина", "Діаметр"},
    "ready_rig": {"PE", "Розмір упаковки", "Довговічність", "Діаметр"},
    "camping_fuel": {"Тип атрактанту", "Аромат/склад"},
    "jig_head": {"PE", "Діаметр", "Розривне навантаження"},
    "jig_winter": {"PE", "Кастинг-тест"},
    "rigging": {"PE", "Кастинг-тест", "Розривне навантаження"},
    "grain_bait": {"Діаметр", "Розривне навантаження"},
    "other": {"PE", "Кастинг-тест", "Матеріал бланка", "Тип рукояті", "Тип пропускних кілець", "Кількість секцій"},
    "tools": {"PE", "Кастинг-тест"},
    "rod_rest_accessory": {"Кастинг-тест", "Кількість секцій"},
    "nod": {"PE", "Матеріал бланка", "Кількість секцій", "Тип рукояті", "Тип пропускних кілець", "Транспортна довжина", "Транспортна довжина (см)"},
}

FAMILY_PARENT_FALLBACKS = {
    "spinning": "Вудилища / Спінінгові",
    "float_rod": "Вудилища / Махові",
    "reel": "Котушки / Спінінгові",
    "spinner": "Приманки / блешні",
    "wobbler": "Приманки / воблери",
    "silicone_lure": "Приманки / мандула",
    "balancer": "Приманки / балансири",
    "jig_winter": "Зимова ловля / мормишки",
    "line": "Волосінь та шнури / волосінь",
    "fluorocarbon": "Волосінь та шнури / флюорокарбон",
    "shock_leader": "Волосінь та шнури / повідковий матеріал",
    "ready_leader": "Волосінь та шнури / готові повідці",
    "float": "Херабуна / поплавки",
    "keepnet": "Підсаки, Садки, кукани / Садки кукани",
    "landing_net": "Підсаки, Садки, кукани / Підсаки",
    "clothing": "Туризм / одяг та взуття",
    "hook": "Гачки",
    "feeder": "Все для монтажу / Годівниці",
    "weight": "Все для монтажу / грузила / спінінгові",
    "swivel": "Все для монтажу / карабіни вертлюги та кільця",
    "groundbait": "Прикормка / Інші бренди",
    "foam_paste": "Прикормка / Макуха",
    "pellets": "Пелетси / Інші бренди",
    "boilie": "Насадочні / бойли",
    "pop_up_bait": "Насадочні / поп-ап",
    "liquid_attractant": "ліквіди і атрактанти / всі",
    "pva_material": "PVA матеріали та аксесуари / PVA матеріали",
    "rod_tube": "Чохли / всі",
    "chair": "Крісла, стільці та столи / стільці",
    "tackle_box": "Відра, сумки та органайзери / коробки органайзери",
    "bag": "Відра, сумки та органайзери / сумки",
    "gift_certificate": "Подарункові сертифікати / всі",
    "camping_fuel": "Туризм / плити, горілки балони",
    "battery": "Туризм / батарейки",
    "flashlight": "Туризм / ліхтарі",
}

ALLOWED_PARENT_PREFIXES_BY_FAMILY = {
    "spinning": ("Вудилища /",),
    "float_rod": ("Вудилища /", "Херабуна / вудилища", "Зимова ловля / вудилища"),
    "reel": ("Котушки /", "Зимова ловля / аксесуари"),
    "hook": ("Гачки", "Херабуна / гачки і повідки"),
    "feeder": ("Все для монтажу / Годівниці",),
    "weight": ("Все для монтажу / грузила",),
    "swivel": ("Все для монтажу / карабіни вертлюги та кільця",),
    "groundbait": ("Прикормка /",),
    "foam_paste": ("Херабуна / Тісто", "Прикормка /"),
    "pellets": ("Пелетси /",),
    "boilie": ("Насадочні / бойли",),
    "pop_up_bait": ("Насадочні / поп-ап",),
    "liquid_attractant": ("ліквіди і атрактанти /", "Насадочні / діпи"),
    "pva_material": ("PVA матеріали та аксесуари /",),
    "line": ("Волосінь та шнури /",),
    "fluorocarbon": ("Волосінь та шнури /",),
    "shock_leader": ("Волосінь та шнури /",),
    "ready_leader": ("Волосінь та шнури /",),
    "wobbler": ("Приманки / воблери",),
    "spinner": ("Приманки / блешні",),
    "silicone_lure": ("Приманки / мандула",),
    "balancer": ("Приманки / балансири",),
    "jig_winter": ("Зимова ловля / мормишки",),
    "float": ("Херабуна / поплавки",),
    "keepnet": ("Підсаки, Садки, кукани / Садки кукани", "Херабуна / підсак, садок"),
    "landing_net": ("Підсаки, Садки, кукани /", "Херабуна / підсак, садок"),
    "rod_tube": ("Чохли /",),
    "chair": ("Крісла, стільці та столи /",),
    "tackle_box": ("Відра, сумки та органайзери /", "Зимова ловля / сані"),
    "bag": ("Відра, сумки та органайзери /",),
    "clothing": ("Туризм / одяг та взуття",),
    "camping_fuel": ("Туризм / плити, горілки балони",),
    "battery": ("Туризм / батарейки",),
    "flashlight": ("Туризм / ліхтарі",),
}

PARAM_NAME_ALIASES = {
    "Тест": "Кастинг-тест",
    "Країна виробник": "Країна-виробник",
    "Країна виробництва": "Країна-виробник",
    "Країна походження": "Країна-виробник",
    "Країна-виробник": "Країна-виробник",
    "Колір/покриття": "Колір",
    "Колір/розмальовка": "Колір",
    "Кольори": "Колір",
    "Кольорова гама": "Колір",
    "Кольорова гамма": "Колір",
    "Кольорове покриття": "Колір",
    "Пакування": "Упаковка",
    "Вид упаковки": "Упаковка",
    "Спосіб упаковки": "Упаковка",
    "Склад/аромат": "Аромат/склад",
    "Обсяг": "Об'єм",
    "Кількість у упаковці": "Кількість в упаковці",
    "Кількість в комплекті": "Комплектація",
    "Кількість в наборі": "Комплектація",
    "Кількість предметів у наборі": "Комплектація",
    "Кількість крючків": "Кількість гачків",
    "Діаметр наживки": "Діаметр",
    "Об'єм упаковки": "Об'єм",
    "Форма випуску": "Форма",
    "Фініш": "Покриття",
    "Лад": "Стрій",
    "Кількість полок": "Кількість полиць",
    "Кількість поличок": "Кількість полиць",
    "Кількість ячеек": "Кількість відділень",
    "Кількість відділів": "Кількість відділень",
    "Кількість відсіків": "Кількість відділень",
    "Вага упаковки": "Вага",
}

DROP_PARAM_NAMES = {
    "Валюта",
    "Сума",
    "Сумма",
    "Бренд",
    "ТМ",
    "Виробник",
    "Модель",
    "Розміри",
    "Гарантія",
    "Клас",
    "Метод",
    "Кількість варіантів",
    "Стійкість до корозії",
    "Діапазон температури використання",
}

UNKNOWN_PARAM_VALUES = {"Не вказано", "не вказано", "Невідомо", "невідомо", "-", "—", "N/A", "n/a"}

BRAND_SPELLING_REPLACEMENTS = {
    "Фанатік": "Fanatik",
}


def normalize_brand_spellings(text: str) -> str:
    normalized = text or ""
    for source, target in BRAND_SPELLING_REPLACEMENTS.items():
        normalized = normalized.replace(source, target)
    return normalized

PREFER_PARSED_PARAM_KEYS = {
    "Тип",
    "Матеріал",
    "Форма",
    "Форма грузила",
    "Умови використання",
    "Призначення",
}

FORCE_TEMPLATE_DESCRIPTION_FAMILIES = {
    "tools",
    "jig_head",
    "pva_material",
    "weight",
    "hook",
    "nod",
    "clothing",
    "swivel",
    "float",
    "keepnet",
    "landing_net",
    "ready_rig",
    "ready_leader",
    "rod_tube",
    "feeder",
    "chair",
    "tackle_box",
    "groundbait",
    "foam_paste",
    "gift_certificate",
    "camping_fuel",
    "battery",
    "flashlight",
}

CATEGORY_TOP_BRANDS = {
    "3K": "3K BAITS",
    "BOUNTY": "BOUNTY",
    "INTERKRIL": "INTERKRIL",
    "ANVIFISHING": "AnviFishing",
    "RPF": "RPF",
    "PUHACH": "Puhach Baits",
    "FSHING MIX": "Fishing Mix",
    "FISHING MIX": "Fishing Mix",
    "REALFISH": "RealFish",
    "FANATIK": "Fanatik",
    "BOOM": "BOOM",
}


def normalize_spaces(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def strip_html(text: str) -> str:
    import re

    no_tags = re.sub(r"<[^>]+>", " ", text or "")
    return normalize_spaces(html.unescape(no_tags))


def wrap_plain_text(text: str) -> str:
    clean = strip_html(text)
    if not clean:
        return ""
    return f"<p>{html.escape(clean)}</p>"


def clean_brand(brand: str) -> str:
    clean = normalize_spaces(brand)
    if not clean:
        return ""
    if clean.lower() in NOT_A_BRAND:
        return ""
    return clean


def infer_brand_from_text(*parts: str, alias_overrides: dict[str, str] | None = None) -> str:
    haystack = f" {' | '.join(normalize_spaces(part).lower() for part in parts if normalize_spaces(part))} "
    if not haystack.strip():
        return ""
    for alias, canonical in (alias_overrides or {}).items():
        marker = normalize_spaces(alias).lower()
        if marker and marker in haystack:
            return normalize_spaces(canonical)
    for canonical, aliases in BRAND_ALIASES:
        for alias in aliases:
            marker = alias.lower()
            if " " in marker or "." in marker or "-" in marker:
                if marker in haystack:
                    return canonical
            elif re.search(rf"(?<![A-Za-z0-9]){re.escape(marker)}(?![A-Za-z0-9])", haystack, flags=re.IGNORECASE):
                return canonical
    return ""


def is_suspicious_name(name: str) -> bool:
    clean = normalize_spaces(name)
    if not clean:
        return True
    return any(pattern.fullmatch(clean) for pattern in SUSPICIOUS_NAME_PATTERNS)


def has_suspicious_text(value: str) -> bool:
    clean = normalize_spaces(strip_html(value)).lower()
    if not clean:
        return False
    return any(token in clean for token in ("wterterwer", "werterwer", "asdfasdf", "qwerty"))


def has_low_quality_description(value: str) -> bool:
    clean = normalize_spaces(strip_html(value))
    if not clean:
        return False
    lower = clean.lower()
    if len(clean) < 350:
        return True
    if lower.count("ідеальний") >= 2:
        return True
    if any(
        phrase in lower
        for phrase in (
            "ідеальний вибір",
            "ідеальним вибором",
            "ідеально підходить",
            "ідеально підходяще",
            "ідеально підход",
            "ідеальним рішенням",
            "найкращих результатів",
            "високоякісного матеріалу",
            "незамінний інструмент",
            "незамінний елемент",
            "незамінним інструментом",
        )
    ):
        return True
    if re.search(r"\b(?:тест|test)\b", lower):
        return True
    if clean.count(".") < 3:
        return True
    return False


def sanitize_description_html(value: str) -> str:
    return (value or "").replace("—", "-").replace("–", "-")


def infer_brand_from_category_path(category_path: list[str] | None) -> str:
    if not category_path:
        return ""
    top = normalize_spaces(category_path[0]).upper()
    return CATEGORY_TOP_BRANDS.get(top, "")


def title_without_duplicate_prefix(title: str, type_word: str) -> str:
    clean = normalize_spaces(title)
    clean = re.sub(r"\s+[\\/]\s*", " ", clean).strip(" -/\\")
    prefix = normalize_spaces(type_word)
    if not clean or not prefix:
        return clean
    doubled = f"{prefix} {prefix} "
    if clean.lower().startswith(doubled.lower()):
        return normalize_spaces(prefix + " " + clean[len(doubled) :])
    return clean


def clean_public_title(title: str, family: str) -> str:
    clean = normalize_spaces(title)
    if family:
        clean = clean.replace("—", "-").replace("–", "-")
        clean = re.sub(r"\s+([,.;:])", r"\1", clean)
        clean = re.sub(r",(?=\S)", ", ", clean)
        clean = re.sub(r"\(\s*шт\.?\s*\)", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bшт\.?\b", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bс/к\b", "з кільцями", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bб/к\b", "без кілець", clean, flags=re.IGNORECASE)
        clean = re.sub(r"(?i)(^|\s)(?:тест|test)(?=\s|$)", " ", clean)
        clean = re.sub(r"^Годівниця\s+Годівниці\b", "Годівниця", clean, flags=re.IGNORECASE)
        clean = re.sub(r"^Спінінг\s+Спиннинг\b", "Спінінг", clean, flags=re.IGNORECASE)
        clean = re.sub(r"^Вантаж/грузило\s+Груз\b", "Грузило", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bГруз\b", "Грузило", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bнабор\b", "набір", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bСеть\b", "Сітка", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bбыстрорастворимая\b", "швидкорозчинна", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bЖидкая\s+Латка\b", "Рідка латка", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bкрюч(?:ки|ок|ків)?\b", "гачки", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bСпиннинг\b", "Спінінг", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bлеск[аиуы]?\b", "волосінь", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bудилище\b", "вудилище", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bудочка\b", "вудка", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bтелескопическое\b", "телескопічне", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bмаховое\b", "махове", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bкольцами\b", "кільцями", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bкомлект\b", "комплект", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bдудочок\b", "вудочок", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bвуд\.(?=\d)", "вудилищ ", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bшвидкоз\.", "Швидкознімний ", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\b1уп\s*=\s*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\(\s*\d+\s*\)", "", clean)
        clean = re.sub(r"^Спінінг\s+Вудилище\b", "Вудилище", clean, flags=re.IGNORECASE)
        clean = re.sub(r"^Спінінг\s+Вудка\b", "Вудка", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bFishing\s*/\s*(\d)", r"Fishing \1", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bProfessinal\b", "Professional", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\b20ib\b", "20 lb", clean, flags=re.IGNORECASE)
        clean = re.sub(r"20\s+lb\s*/\s*\d+\b", "20 lb", clean, flags=re.IGNORECASE)
        clean = re.sub(r"^Повідець\s+Повіець\b", "Повідець", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\b([А-Яа-яA-Za-zІіЇїЄєҐґ0-9]{4,})\s+\1\b", r"\1", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\(\s*\)", "", clean)
        clean = re.sub(r"\s+([,.;:])", r"\1", clean)
    return normalize_spaces(clean)


def xml_escape(text: str) -> str:
    return escape((text or "").translate(INVALID_XML_CHARS), {'"': "&quot;", "'": "&apos;"})


def cdata(text: str) -> str:
    if not text:
        return ""
    safe = str(text).translate(INVALID_XML_CHARS).replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{safe}]]>"


def load_products(limit: int | None = None) -> list[dict[str, Any]]:
    payload = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))
    deduped: dict[str, dict[str, Any]] = {}
    for product in payload.get("products", []):
        kod = normalize_spaces(product.get("kod", ""))
        name = normalize_spaces(product.get("name", ""))
        if not kod or not name or name in SKIP_NAMES:
            continue
        deduped[kod] = product
        if limit and len(deduped) >= limit:
            break
    return list(deduped.values())


def load_overrides() -> dict[str, Any]:
    if not OVERRIDES_JSON.exists():
        return {
            "products": {},
            "brand_aliases": {},
            "family_parent_overrides": {},
            "article_parent_overrides": {},
            "article_brand_overrides": {},
        }
    payload = json.loads(OVERRIDES_JSON.read_text(encoding="utf-8"))
    return {
        "products": payload.get("products") or {},
        "brand_aliases": payload.get("brand_aliases") or {},
        "family_parent_overrides": payload.get("family_parent_overrides") or {},
        "article_parent_overrides": payload.get("article_parent_overrides") or {},
        "article_brand_overrides": payload.get("article_brand_overrides") or {},
    }


def load_meta_map() -> dict[str, dict[str, Any]]:
    if not META_DB.exists():
        return {}

    out: dict[str, dict[str, Any]] = {}
    conn = sqlite3.connect(META_DB)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT v.kod, v.name_raw, v.test_min, v.test_max, v.length_m, v.action,
                   v.delta_params_json, v.pictures_json,
                   m.parent_key, m.family, m.brand, m.model_name, m.display_name, m.type_word,
                   m.source_category, m.description_html, m.common_params_json, m.status
            FROM variants v
            JOIN models m ON m.parent_key = v.parent_key
            """
        ).fetchall()
        for row in rows:
            out[row["kod"]] = {
                "parent_key": row["parent_key"],
                "family": row["family"],
                "brand": row["brand"] or "",
                "model_name": row["model_name"] or "",
                "display_name": row["display_name"] or "",
                "type_word": row["type_word"] or "",
                "source_category": row["source_category"] or "",
                "description_html": row["description_html"] or "",
                "meta_status": row["status"] or "",
                "common_params": json.loads(row["common_params_json"] or "{}"),
                "delta_params": json.loads(row["delta_params_json"] or "{}"),
                "test_min": row["test_min"],
                "test_max": row["test_max"],
                "length_m": row["length_m"],
                "action": row["action"],
                "name_raw": row["name_raw"] or "",
                "pictures": json.loads(row["pictures_json"] or "[]"),
            }
    finally:
        conn.close()
    return out


def merge_param_maps(*param_maps: dict[str, Any]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for param_map in param_maps:
        for key, value in (param_map or {}).items():
            text = normalize_spaces(value)
            if key and text:
                merged[key] = text
    return merged


def build_meta_context(product: dict[str, Any], meta: dict[str, Any], parsed) -> dict[str, Any]:
    ctx = {
        "family": "",
        "brand": "",
        "model_name": "",
        "display_name": normalize_spaces(product.get("name", "")),
        "type_word": "",
        "source_category": "",
        "description_html": "",
        "common_params": {},
        "delta_params": {},
        "test_min": None,
        "test_max": None,
        "length_m": None,
        "action": None,
        "pictures": [],
    }
    if parsed:
        ctx.update(
            {
                "family": parsed.family,
                "brand": parsed.brand,
                "model_name": parsed.model_name,
                "display_name": parsed.display_name,
                "type_word": parsed.type_word,
                "common_params": dict(parsed.common_params),
                "delta_params": dict(parsed.delta_params),
                "test_min": parsed.test_min,
                "test_max": parsed.test_max,
                "length_m": parsed.length_m,
                "action": parsed.action,
            }
        )
    parsed_family = normalize_spaces(parsed.family if parsed else "")
    meta_family = normalize_spaces(meta.get("family", "") if meta else "")
    family_changed = bool(parsed_family and meta_family and parsed_family != meta_family)
    reset_meta_params = family_changed and parsed_family in {"foam_paste"}

    if meta:
        carry_meta_keys = ["brand", "model_name"] if family_changed else ["brand", "model_name", "display_name", "source_category"]
        if not family_changed:
            carry_meta_keys.append("description_html")
        for key in carry_meta_keys:
            if normalize_spaces(meta.get(key, "")):
                ctx[key] = meta[key]
        if not parsed_family or parsed_family == "other":
            for key in ("family", "type_word"):
                if normalize_spaces(meta.get(key, "")):
                    ctx[key] = meta[key]
        for key in ("test_min", "test_max", "length_m", "action"):
            if not reset_meta_params and meta.get(key) not in (None, ""):
                ctx[key] = meta[key]
        if reset_meta_params:
            ctx["common_params"] = merge_param_maps(ctx["common_params"])
            ctx["delta_params"] = merge_param_maps(ctx["delta_params"])
        elif family_changed:
            ctx["common_params"] = merge_param_maps(meta.get("common_params") or {}, ctx["common_params"])
            ctx["delta_params"] = merge_param_maps(meta.get("delta_params") or {}, ctx["delta_params"])
        else:
            ctx["common_params"] = merge_param_maps(ctx["common_params"], meta.get("common_params") or {})
            ctx["delta_params"] = merge_param_maps(ctx["delta_params"], meta.get("delta_params") or {})
        ctx["pictures"] = [pic for pic in (meta.get("pictures") or []) if normalize_spaces(pic)]

    if parsed:
        for key in PREFER_PARSED_PARAM_KEYS:
            parsed_val = normalize_spaces((parsed.common_params or {}).get(key, "") or (parsed.delta_params or {}).get(key, ""))
            current_val = normalize_spaces((ctx["common_params"] or {}).get(key, "") or (ctx["delta_params"] or {}).get(key, ""))
            if parsed_val and (not current_val or current_val in UNKNOWN_PARAM_VALUES or current_val != parsed_val):
                if key in (ctx["delta_params"] or {}):
                    ctx["delta_params"][key] = parsed_val
                else:
                    ctx["common_params"][key] = parsed_val
    return ctx


def collect_param_pairs(ctx: dict[str, Any]) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = []
    seen: set[str] = set()

    def push(key: str, value: Any) -> None:
        clean_key = normalize_spaces(key)
        clean_val = normalize_spaces(value)
        if not clean_key or not clean_val or clean_key in seen:
            return
        params.append((clean_key, clean_val))
        seen.add(clean_key)

    for key, value in (ctx.get("common_params") or {}).items():
        push(key, value)
    for key, value in (ctx.get("delta_params") or {}).items():
        push(key, value)
    if ctx.get("test_min") is not None and ctx.get("test_max") is not None:
        push("Кастинг-тест", f"{ctx['test_min']:g}-{ctx['test_max']:g} г")
    if ctx.get("length_m"):
        push("Довжина", f"{ctx['length_m']:g} м")
    if ctx.get("action"):
        push("Лад", ctx["action"])
    return params


def sanitize_param_pairs(family: str, params: list[tuple[str, str]]) -> list[tuple[str, str]]:
    blocked = DROP_PARAMS_BY_FAMILY.get(family, set())
    cleaned: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key, value in params:
        key = PARAM_NAME_ALIASES.get(key, key)
        if key in blocked:
            continue
        if key in DROP_PARAM_NAMES:
            continue
        if value in UNKNOWN_PARAM_VALUES:
            continue
        if family in {"line", "fluorocarbon", "shock_leader", "ready_leader"} and key == "Матеріал" and value.lower() == "силікон":
            continue
        # старий AI-генератор ліпив "Тип вудилища: Спінінг" на махові вудки
        if family == "float_rod" and key == "Тип вудилища" and value.lower().startswith("спінінг"):
            value = "Махова"
        # "Країна-виробник" зі старого AI — недовірене; перевірене значення
        # додає param_enrichment за мапою брендів
        if key == "Країна-виробник":
            continue
        if key in seen:
            continue
        seen.add(key)
        cleaned.append((key, value))
    return cleaned


FLOAT_WEIGHT_RE = re.compile(r"(?<!\d)(\d+(?:[,.]\d+)?(?:\s*\+\s*\d+(?:[,.]\d+)?)?)\s*(?:gr|гр|г)\b", re.IGNORECASE)


def enrich_obvious_param_pairs(family: str, title: str, params: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Add only high-confidence params that are explicit from family or title."""
    enriched = list(params)
    seen = {name for name, _ in enriched}
    title_l = normalize_spaces(title).lower()

    def push(name: str, value: str) -> None:
        if name not in seen and normalize_spaces(value):
            enriched.append((name, value))
            seen.add(name)

    if family == "swivel":
        if "караб" in title_l:
            push("Тип", "Карабін")
        elif "вертлю" in title_l:
            push("Тип", "Вертлюг")
        elif "кільц" in title_l or "кольц" in title_l:
            push("Тип", "Кільце")
        else:
            push("Тип", "Риболовна фурнітура")
        push("Матеріал", "Метал")
        push("Призначення", "Монтаж оснастки")

    if family == "float":
        push("Тип", "Поплавок")
        push("Призначення", "Поплавкова ловля")
        weight_match = FLOAT_WEIGHT_RE.search(title)
        if weight_match:
            push("Вага", f"{normalize_spaces(weight_match.group(1)).replace(',', '.')} г")

    if family == "float_rod":
        # уточнюємо тип вудки за маркерами в назві (не вгадуємо, де маркера немає)
        if "боло" in title_l or "bolo" in title_l or "с\\к" in title_l or "с/к" in title_l:
            rod_type = "Болонська"
        elif "б/к" in title_l or "б\\к" in title_l or "без кілець" in title_l or "без килець" in title_l:
            rod_type = "Махова"
        elif "телескоп" in title_l or "тел-" in title_l:
            rod_type = "Телескопічна"
        else:
            rod_type = ""
        if rod_type:
            enriched = [(k, rod_type if k == "Тип вудилища" else v) for k, v in enriched]
            if "Тип вудилища" not in seen:
                enriched.append(("Тип вудилища", rod_type))
                seen.add("Тип вудилища")

    return enriched


def choose_parent_path(
    product: dict[str, Any],
    family: str,
    raw_name: str,
    family_parent_overrides: dict[str, str] | None = None,
    article_parent_overrides: dict[str, str] | None = None,
) -> str:
    article = normalize_spaces(product.get("kod", ""))
    if article_parent_overrides:
        article_override = normalize_spaces(article_parent_overrides.get(article, ""))
        if article_override:
            return article_override
    current = map_product_to_target_path(product)
    family_override = normalize_spaces((family_parent_overrides or {}).get(family, ""))
    fallback = family_override or FAMILY_PARENT_FALLBACKS.get(family)
    if not fallback:
        return current
    if family == "foam_paste":
        lowered = raw_name.lower()
        if "herabuna" in lowered or "херабун" in lowered or current.lower() == "херабуна / тісто":
            return "Херабуна / тісто"
    allowed_prefixes = ALLOWED_PARENT_PREFIXES_BY_FAMILY.get(family)
    if allowed_prefixes and not any(current == prefix or current.startswith(prefix) for prefix in allowed_prefixes):
        return fallback
    if family == "line":
        lowered = raw_name.lower()
        if "шнур" in lowered:
            return "Волосінь та шнури / шнури"
        if "флюр" in lowered or "флюоро" in lowered:
            return "Волосінь та шнури / флюорокарбон"
        if "повідец" in lowered or "повод" in lowered:
            return "Волосінь та шнури / готові повідці"
    if family == "spinner" and current not in {"Приманки / блешні", "Приманки / балансири"}:
        return fallback
    if family in {"wobbler", "silicone_lure", "balancer", "jig_winter", "fluorocarbon", "shock_leader", "ready_leader", "clothing", "hook", "gift_certificate", "camping_fuel", "battery", "flashlight"}:
        return fallback
    if family == "line" and current not in {"Волосінь та шнури / волосінь", "Волосінь та шнури / шнури", "Волосінь та шнури / флюорокарбон", "Волосінь та шнури / готові повідці", "Волосінь та шнури / повідковий матеріал"}:
        return fallback
    return current


def build_description(product: dict[str, Any], ctx: dict[str, Any]) -> str:
    raw = normalize_spaces(product.get("descr_big", ""))
    product_name = normalize_spaces(product.get("name", ""))
    family = normalize_spaces(ctx.get("family", ""))
    meta_description = normalize_spaces(ctx.get("description_html", ""))
    if (
        family not in FORCE_TEMPLATE_DESCRIPTION_FAMILIES
        and meta_description
        and ctx.get("meta_status") == "approved"
        and not has_suspicious_text(meta_description)
        and not has_low_quality_description(meta_description)
    ):
        return sanitize_description_html(ctx["description_html"])
    if family not in FORCE_TEMPLATE_DESCRIPTION_FAMILIES and raw and not has_suspicious_text(raw) and not has_low_quality_description(raw):
        return sanitize_description_html(wrap_plain_text(raw))
    clean_ctx = dict(ctx)
    clean_ctx["article"] = normalize_spaces(product.get("kod", ""))  # унікальний сід фраз
    if (
        family in FORCE_TEMPLATE_DESCRIPTION_FAMILIES
        or ctx.get("meta_status") != "approved"  # ai_draft НЕ пропускаємо і у варіантний шлях
        or has_suspicious_text(meta_description)
        or has_low_quality_description(meta_description)
    ):
        clean_ctx["description_html"] = ""
    if has_suspicious_text(clean_ctx.get("display_name", "")):
        clean_ctx["display_name"] = product_name
    if has_suspicious_text(clean_ctx.get("name_raw", "")):
        clean_ctx["name_raw"] = product_name
    clean_ctx["display_name"] = clean_public_title(str(clean_ctx.get("display_name") or product_name), family)
    clean_ctx["name_raw"] = clean_public_title(str(clean_ctx.get("name_raw") or product_name), family)
    fallback = resolve_description_html(clean_ctx, product_name)
    return sanitize_description_html(fallback) if normalize_spaces(strip_html(fallback)) else ""


def build_canonical_products(limit: int | None = None) -> list[dict[str, Any]]:
    products = load_products(limit=limit)
    meta_map = load_meta_map()
    overrides = load_overrides()
    product_overrides = overrides["products"]
    brand_aliases = overrides["brand_aliases"]
    family_parent_overrides = overrides["family_parent_overrides"]
    article_parent_overrides = overrides["article_parent_overrides"]
    article_brand_overrides = overrides["article_brand_overrides"]
    items: list[dict[str, Any]] = []

    for product in products:
        kod = normalize_spaces(product.get("kod", ""))
        product_override = product_overrides.get(kod) or {}
        if product_override.get("exclude"):
            continue
        raw_name = normalize_spaces(product.get("name", ""))
        if is_suspicious_name(raw_name):
            continue
        qty = max(0, int(round(float(product.get("stock") or 0))))
        price = float(product.get("cena_r") or product.get("cena_o") or 0)
        parsed = parse_product(product)
        meta = meta_map.get(kod, {})
        ctx = build_meta_context(product, meta, parsed)

        parsed_brand = clean_brand(parsed.brand if parsed else "")
        meta_brand = clean_brand(meta.get("brand", "") if meta else "")
        raw_brand = clean_brand(product.get("proizv", ""))
        category_brand = clean_brand(infer_brand_from_category_path(product.get("category_path") or []))
        inferred_brand = infer_brand_from_text(
            raw_name,
            ctx.get("display_name", ""),
            meta.get("display_name", "") if meta else "",
            alias_overrides=brand_aliases,
        )
        override_brand = clean_brand(article_brand_overrides.get(kod, ""))
        brand = override_brand or parsed_brand or meta_brand or raw_brand or inferred_brand or category_brand

        meta_title = normalize_spaces(meta.get("display_name", "") if meta else "")
        parsed_title = normalize_spaces(parsed.display_name if parsed else "")
        meta_family = normalize_spaces(meta.get("family", "") if meta else "")
        parsed_family = normalize_spaces(parsed.family if parsed else "")
        if parsed_title and parsed_family and meta_family and parsed_family != meta_family:
            title_seed = parsed_title
        elif parsed_title and brand and parsed_brand and parsed_brand != meta_brand:
            title_seed = parsed_title
        else:
            title_seed = meta_title or parsed_title or normalize_spaces(ctx.get("display_name", "") or raw_name)
        display_title = build_variant_title(title_seed, ctx)
        family = normalize_spaces(ctx.get("family", ""))
        display_title = title_without_duplicate_prefix(display_title, normalize_spaces(ctx.get("type_word", "")))
        display_title = clean_public_title(display_title, family)
        display_title = normalize_spaces(display_title or raw_name)
        # ПОЛІТИКА (вимога власниці, 2026-07-11): публічна назва на сайті =
        # ТОЧНО назва з УкрСкладу (щоб товари шукались однаково в обох системах).
        # Оздоблена display_title лишається для описів/аналітики.
        title = raw_name

        description = build_description(product, ctx)
        param_pairs = enrich_obvious_param_pairs(
            family,
            title,
            sanitize_param_pairs(family, collect_param_pairs(ctx)),
        )
        from param_enrichment import enrich as _mass_enrich
        param_pairs = _mass_enrich(family, title, brand, param_pairs)
        params = [
            {"name": k, "value": normalize_brand_spellings(v)}
            for k, v in param_pairs
        ]
        parent = choose_parent_path(
            product,
            family,
            f"{raw_name} {title}",
            family_parent_overrides=family_parent_overrides,
            article_parent_overrides=article_parent_overrides,
        )
        title = normalize_brand_spellings(title)
        description = normalize_brand_spellings(description)

        item: dict[str, Any] = {
            "article": kod,
            "title": title,
            "parent": parent,
            "price": price,
            "currency": "UAH",
            "display_in_showcase": 1 if int(product.get("visible") or 0) else 0,
            "presence": "В наявності" if qty > 0 else "Немає в наявності",
            "presence_api": "in stock" if qty > 0 else "out of stock",
            "quantity": qty,
            "description": description,
            "params": params,
            "images": [pic for pic in ctx.get("pictures", []) if normalize_spaces(pic)],
            "family": family,
            "source_name": raw_name,
            "suspicious_name": is_suspicious_name(raw_name),
        }
        if brand:
            item["brand"] = brand
        items.append(item)

    by_title: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_title[item["title"]].append(item)
    for title, title_items in by_title.items():
        if len(title_items) < 2:
            continue
        # Спершу людський суфікс: номер гачка/розмір з артикула виду "A6006#9" → "№9".
        # Якщо це не дає унікальності — технічний fallback "[артикул]".
        proposed: dict[int, str] = {}
        for idx, item in enumerate(title_items):
            m = re.search(r"#(\d+(?:/\d+)?)$", str(item["article"]))
            if m and f"№{m.group(1)}" not in title:
                proposed[idx] = f"{title} №{m.group(1)}"
            else:
                proposed[idx] = f"{title} (арт. {item['article']})"
        if len(set(proposed.values())) == len(title_items):
            for idx, item in enumerate(title_items):
                item["title"] = proposed[idx]
        else:
            for item in title_items:
                item["title"] = f"{title} (арт. {item['article']})"

    return sorted(items, key=lambda item: (item["parent"], item["title"], item["article"]))


def collect_param_headers(products: list[dict[str, Any]]) -> list[str]:
    names = Counter()
    for product in products:
        for param in product.get("params", []):
            names[normalize_spaces(param.get("name", ""))] += 1

    ordered: list[str] = []
    seen: set[str] = set()
    for name in PARAM_PRIORITY:
        if name in names:
            ordered.append(name)
            seen.add(name)
    for name in sorted(names):
        if name not in seen:
            ordered.append(name)
    return ordered


def build_category_tree() -> tuple[list[dict[str, Any]], dict[str, int]]:
    categories: list[dict[str, Any]] = []
    path_to_id: dict[str, int] = {}
    next_id = 1

    def walk(nodes: list[dict[str, Any]], parent_id: int | None = None, parent_path: str = "") -> None:
        nonlocal next_id
        for node in nodes:
            name = normalize_spaces(node.get("name", ""))
            if not name:
                continue
            current_path = f"{parent_path} / {name}".strip(" /")
            categories.append({"id": next_id, "parentId": parent_id, "name": name, "path": current_path})
            path_to_id[current_path] = next_id
            current_id = next_id
            next_id += 1
            children = [child for child in (node.get("subcategories") or []) if isinstance(child, dict)]
            if children:
                walk(children, current_id, current_path)

    walk(STRUCTURE["categories"])
    return categories, path_to_id


def build_category_path(path: str, path_to_id: dict[str, int]) -> int | None:
    clean_path = normalize_spaces(path)
    if clean_path in path_to_id:
        return path_to_id[clean_path]
    leaf = clean_path.split(" / ")[-1]
    for candidate, cat_id in path_to_id.items():
        if candidate.endswith(leaf):
            return cat_id
    return None


def build_horoshop_yml_lines(products: list[dict[str, Any]], categories: list[dict[str, Any]], path_to_id: dict[str, int]) -> list[str]:
    used_paths = {item["parent"] for item in products}
    used_ids: set[int] = set()
    for path in used_paths:
        cat_id = build_category_path(path, path_to_id)
        if cat_id:
            used_ids.add(cat_id)
    changed = True
    while changed:
        changed = False
        for cat in categories:
            if cat["id"] in used_ids and cat["parentId"] and cat["parentId"] not in used_ids:
                used_ids.add(cat["parentId"])
                changed = True

    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(f'<yml_catalog date="{datetime.now().strftime("%Y-%m-%d %H:%M")}">')
    lines.append("  <shop>")
    lines.append("    <name>Все для рибалки</name>")
    lines.append("    <currencies><currency id=\"UAH\" rate=\"1\"/></currencies>")
    lines.append("    <categories>")
    for cat in categories:
        if cat["id"] not in used_ids:
            continue
        parent_attr = f' parentId="{cat["parentId"]}"' if cat["parentId"] else ""
        lines.append(f'      <category id="{cat["id"]}"{parent_attr}>{xml_escape(cat["name"])}</category>')
    lines.append("    </categories>")
    lines.append("    <offers>")
    # гарантований корінь-фолбек: перша топ-категорія дерева (щоб НІЩО не зникало)
    root_fallback_id = next((c["id"] for c in categories if not c["parentId"]), None)
    for product in products:
        cat_id = build_category_path(product["parent"], path_to_id)
        if not cat_id:
            # товар з нерозпізнаною категорією НЕ викидаємо: кладемо у family-fallback,
            # інакше — у гарантований корінь. Реальний товар у наявності не має зникати.
            fb_path = FAMILY_PARENT_FALLBACKS.get(product.get("family", ""))
            if isinstance(fb_path, str):
                cat_id = build_category_path(fb_path, path_to_id)
            if not cat_id:
                cat_id = root_fallback_id
            if not cat_id:
                continue
        article = xml_escape(product["article"])
        title = xml_escape(product["title"])
        available = "true" if product["quantity"] > 0 else "false"
        lines.append(f'      <offer id="{article}" available="{available}">')
        lines.append(f"        <name>{title}</name>")
        lines.append(f"        <name_ua>{title}</name_ua>")
        lines.append(f"        <price>{float(product['price'] or 0):.2f}</price>")
        lines.append("        <currencyId>UAH</currencyId>")
        lines.append(f"        <categoryId>{cat_id}</categoryId>")
        lines.append(f"        <stock_quantity>{int(product['quantity'])}</stock_quantity>")
        lines.append(f"        <article>{article}</article>")
        if product.get("brand"):
            lines.append(f"        <vendor>{xml_escape(product['brand'])}</vendor>")
        for image in product.get("images", []):
            lines.append(f"        <picture>{xml_escape(image)}</picture>")
        if normalize_spaces(product.get("description", "")):
            lines.append(f"        <description>{cdata(product['description'])}</description>")
            lines.append(f"        <description_ua>{cdata(product['description'])}</description_ua>")
        for param in product.get("params", []):
            lines.append(f'        <param name="{xml_escape(param["name"])}">{xml_escape(param["value"])}</param>')
        lines.append("      </offer>")
    lines.append("    </offers>")
    lines.append("  </shop>")
    lines.append("</yml_catalog>")
    return lines


def write_horoshop_xml(out_path: Path = OUT_XML, limit: int | None = None) -> Path:
    products = build_canonical_products(limit=limit)
    categories, path_to_id = build_category_tree()
    lines = build_horoshop_yml_lines(products, categories, path_to_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def audit_products(products: list[dict[str, Any]]) -> dict[str, Any]:
    param_counts = [len(product.get("params", [])) for product in products]
    brand_missing = sum(1 for product in products if not normalize_spaces(product.get("brand", "")))
    desc_missing = sum(1 for product in products if not normalize_spaces(strip_html(product.get("description", ""))))
    suspicious_names = [product for product in products if product.get("suspicious_name")]
    duplicate_articles = Counter(product["article"] for product in products)
    duplicates = [(article, count) for article, count in duplicate_articles.items() if count > 1]
    return {
        "total_products": len(products),
        "with_brand_pct": round((len(products) - brand_missing) / max(len(products), 1) * 100, 1),
        "with_description_pct": round((len(products) - desc_missing) / max(len(products), 1) * 100, 1),
        "avg_param_count": round(sum(param_counts) / max(len(param_counts), 1), 2),
        "low_param_pct": round(sum(1 for count in param_counts if count <= 2) / max(len(param_counts), 1) * 100, 1),
        "duplicate_articles": sorted(duplicates, key=lambda item: (-item[1], item[0]))[:20],
        "suspicious_name_count": len(suspicious_names),
        "suspicious_name_samples": [
            {"article": product["article"], "source_name": product["source_name"], "title": product["title"]}
            for product in suspicious_names[:20]
        ],
    }
