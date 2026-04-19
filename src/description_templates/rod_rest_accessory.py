from __future__ import annotations

from .base import DescriptionContext, build_standard_description


def build_description(ctx: DescriptionContext) -> str:
    intro = f"{ctx.display_name} — аксесуар для підставки, що допомагає стабілізувати робоче місце рибалки."
    usage = "Застосовується у комплекті з род-подами або стійками для надійного розміщення вудилищ."
    return build_standard_description(ctx, intro, usage, ["Тип", "Довжина", "Матеріал"])
