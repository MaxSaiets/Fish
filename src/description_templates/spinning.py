from __future__ import annotations

from .base import DescriptionContext, build_standard_description


def build_description(ctx: DescriptionContext) -> str:
    intro = f"{ctx.display_name} — вудилище для контрольованої проводки та стабільної роботи на різних дистанціях."
    usage = "Підійде для ловлі хижака на річках і водоймах, коли важливі чутливість бланка та точність закидання."
    return build_standard_description(ctx, intro, usage, ["Тип вудилища", "Матеріал", "Тест", "Довжина", "Стрій"])
