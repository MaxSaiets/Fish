from __future__ import annotations

from .base import DescriptionContext, build_standard_description


def build_description(ctx: DescriptionContext) -> str:
    intro = f"{ctx.display_name} — готовий повідець для швидкого монтажу без зайвої підготовки на водоймі."
    usage = "Добрий вибір для ситуацій, коли важливі стабільна повторюваність оснастки та швидка заміна під час кльову."
    return build_standard_description(ctx, intro, usage, ["Тип", "Матеріал", "Призначення", "Довжина", "Розмір"])
