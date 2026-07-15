from __future__ import annotations

from .base import DescriptionContext, build_standard_description, normalize_param_value, pick
from .balancer import build_description as balancer_description
from .bite_indicator import build_description as bite_indicator_description
from .clothing import build_description as clothing_description
from .chair import build_description as chair_description
from .feeder import build_description as feeder_description
from .float_rod import build_description as float_rod_description
from .float import build_description as float_description
from .fluorocarbon import build_description as fluorocarbon_description
from .groundbait import build_description as groundbait_description
from .grain_bait import build_description as grain_bait_description
from .hook import build_description as hook_description
from .jig_head import build_description as jig_head_description
from .jig_winter import build_description as jig_winter_description
from .keepnet import build_description as keepnet_description
from .landing_net import build_description as landing_net_description
from .line import build_description as line_description
from .nod import build_description as nod_description
from .other import build_description as other_description
from .pva_material import build_description as pva_material_description
from .ready_rig import build_description as ready_rig_description
from .ready_leader import build_description as ready_leader_description
from .reel import build_description as reel_description
from .rod_rest_accessory import build_description as rod_rest_accessory_description
from .rod_tube import build_description as rod_tube_description
from .shock_leader import build_description as shock_leader_description
from .silicone_lure import build_description as silicone_lure_description
from .spinner import build_description as spinner_description
from .spinning import build_description as spinning_description
from .swivel import build_description as swivel_description
from .tackle_box import build_description as tackle_box_description
from .tools import build_description as tools_description
from .weight import build_description as weight_description
from .wobbler import build_description as wobbler_description
from .flashlight import build_description as flashlight_description
from .battery import build_description as battery_description
from .camping_fuel import build_description as camping_fuel_description
from .gift_certificate import build_description as gift_certificate_description


DESCRIPTION_BUILDERS = {
    "spinning": spinning_description,
    "float_rod": float_rod_description,
    "float": float_description,
    "line": line_description,
    "fluorocarbon": fluorocarbon_description,
    "shock_leader": shock_leader_description,
    "ready_leader": ready_leader_description,
    "grain_bait": grain_bait_description,
    "boilie": grain_bait_description,
    "pop_up_bait": grain_bait_description,
    "pellets": grain_bait_description,
    "bait_mix": grain_bait_description,
    "liquid_attractant": grain_bait_description,
    "groundbait": groundbait_description,
    "foam_paste": groundbait_description,
    "nod": nod_description,
    "bite_indicator": bite_indicator_description,
    "rod_rest_accessory": rod_rest_accessory_description,
    "pva_material": pva_material_description,
    "reel": reel_description,
    "wobbler": wobbler_description,
    "spinner": spinner_description,
    "silicone_lure": silicone_lure_description,
    "jig_head": jig_head_description,
    "balancer": balancer_description,
    "jig_winter": jig_winter_description,
    "hook": hook_description,
    "swivel": swivel_description,
    "rigging": swivel_description,
    "bag": tackle_box_description,
    "flashlight": flashlight_description,
    "battery": battery_description,
    "camping_fuel": camping_fuel_description,
    "gift_certificate": gift_certificate_description,
    "keepnet": keepnet_description,
    "landing_net": landing_net_description,
    "rod_tube": rod_tube_description,
    "ready_rig": ready_rig_description,
    "feeder": feeder_description,
    "chair": chair_description,
    "tackle_box": tackle_box_description,
    "tools": tools_description,
    "weight": weight_description,
    "clothing": clothing_description,
    "other": other_description,
}


def build_description_html(meta: dict) -> str:
    ctx = DescriptionContext.from_meta(meta)
    builder = DESCRIPTION_BUILDERS.get(ctx.family, other_description)
    return builder(ctx)


def build_variant_description_html(parent_meta: dict, variant_delta: dict) -> str:
    """
    Опис для дочірнього варіанту:
    бере батьківський HTML-опис і додає рядок з унікальними параметрами цього варіанту.
    """
    base_html = parent_meta.get("description_html", "")
    if not base_html:
        base_html = build_description_html(parent_meta)

    # Пріоритетні поля варіанту (відрізняють один розмір від іншого)
    priority_keys = [
        "Довжина", "Тест", "Стрій", "Розмір", "Вага", "Діаметр", "PE",
        "Розривне навантаження", "Розривне навантаження (lb)",
        "Об'єм", "Підшипники", "Кількість в упаковці",
    ]
    family = str(parent_meta.get("family") or "")
    unique_parts: list[str] = []
    seen: set[str] = set()
    label_aliases = {
        "Тест": "Кастинг",
        "Кастинг-тест": "Кастинг",
    }
    # для гачків/фурнітури "PE" — насправді номер розміру, а не плетінка
    if family in {"hook", "swivel", "jig_head", "ready_leader", "rigging", "weight"}:
        label_aliases["PE"] = "Розмір"
    # поля, що НЕ мають сенсу для сім'ї — не виводимо у варіантний рядок
    skip_by_family = {
        "hook": {"Тест", "Кастинг-тест", "Довжина", "Діаметр", "Розривне навантаження"},
        "swivel": {"PE", "Довжина", "Діаметр"} if False else set(),
    }
    skip = skip_by_family.get(family, set())

    def emit(key, val):
        if not val or key in seen or key in skip:
            return
        label = label_aliases.get(key, key)
        # уникаємо дубля міток (напр. і Розмір, і PE→Розмір)
        if label in {label_aliases.get(k, k) for k in seen}:
            seen.add(key)
            return
        val = normalize_param_value(label, str(val))
        unique_parts.append(f"{label.lower()} {val}")
        seen.add(key)

    for key in priority_keys:
        emit(key, variant_delta.get(key))
    for key, val in variant_delta.items():
        emit(key, val)

    if not unique_parts:
        return base_html

    seed = str(parent_meta.get("name_raw") or "") + "|" + "|".join(sorted(seen))
    lead = pick(seed + "|varlead", [
        "Це виконання моделі",
        "Саме ця версія",
        "Ця модель у виконанні",
        "Конкретно це виконання",
    ])
    variant_block = f"<p><em>{lead}: {', '.join(unique_parts)}.</em></p>"
    return base_html + variant_block
