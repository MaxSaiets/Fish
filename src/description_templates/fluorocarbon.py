from __future__ import annotations

from .base import DescriptionContext, build_standard_description


def build_description(ctx: DescriptionContext) -> str:
    intro = f"{ctx.display_name} — флюрокарбон для оснащення, де потрібна малопомітність у воді та зносостійкість."
    usage = "Підходить для повідців і делікатних монтажів на прозорій воді, коли важливі контроль і впевнене виведення."
    return build_standard_description(ctx, intro, usage, ["Тип", "Матеріал", "Діаметр", "Розривне навантаження"])
