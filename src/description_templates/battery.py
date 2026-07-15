from __future__ import annotations
from .base import DescriptionContext, build_standard_description


def build_description(ctx: DescriptionContext) -> str:
    intro = [
        f"{ctx.display_name} — елемент живлення для рибальської електроніки: сигналізаторів, "
        f"ліхтарів, ехолотів і пейджерів.",
        f"{ctx.display_name} — надійне джерело живлення, щоб снасть не підвела в найважливіший "
        f"момент сесії.",
    ]
    usage = [
        "Тримайте запас у монтажній коробці: свіжий комплект під рукою рятує нічну ловлю, "
        "коли сигналізатор раптом замовк.",
        "Стабільна напруга протягом усього ресурсу — електроніка працює передбачувано "
        "від першої до останньої години.",
    ]
    return build_standard_description(ctx, intro, usage, ["Тип", "Призначення", "Кількість в упаковці"])
