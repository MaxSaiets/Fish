from __future__ import annotations

from .base import DescriptionContext, build_standard_description
from .bite_indicator import build_description as bite_indicator_description
from .float_rod import build_description as float_rod_description
from .fluorocarbon import build_description as fluorocarbon_description
from .grain_bait import build_description as grain_bait_description
from .line import build_description as line_description
from .nod import build_description as nod_description
from .other import build_description as other_description
from .ready_leader import build_description as ready_leader_description
from .rod_rest_accessory import build_description as rod_rest_accessory_description
from .shock_leader import build_description as shock_leader_description
from .spinning import build_description as spinning_description


DESCRIPTION_BUILDERS = {
    "spinning": spinning_description,
    "float_rod": float_rod_description,
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
    "nod": nod_description,
    "bite_indicator": bite_indicator_description,
    "rod_rest_accessory": rod_rest_accessory_description,
    "other": other_description,
}


def build_description_html(meta: dict) -> str:
    ctx = DescriptionContext.from_meta(meta)
    builder = DESCRIPTION_BUILDERS.get(ctx.family, other_description)
    return builder(ctx)
