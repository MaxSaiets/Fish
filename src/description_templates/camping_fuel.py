from __future__ import annotations
from .base import DescriptionContext, build_standard_description


def build_description(ctx: DescriptionContext) -> str:
    intro = [
        f"{ctx.display_name} — паливо для туристичних пальників і плиток: гарячий чай і їжа "
        f"на березі за кілька хвилин.",
        f"{ctx.display_name} — компактне джерело вогню для кемпінгу та довгих сесій, коли "
        f"хочеться зігрітися і перекусити не покидаючи точку.",
    ]
    usage = [
        "Сумісне зі стандартними туристичними пальниками; компактний балон легко вміщається "
        "в рюкзаку поряд зі снастями.",
        "Рівне полум'я і передбачувана витрата — одного балона вистачає на кілька виїздів.",
    ]
    return build_standard_description(ctx, intro, usage, ["Тип", "Призначення", "Об'єм"])
