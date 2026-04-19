from __future__ import annotations

from .base import DescriptionContext, build_standard_description


def build_description(ctx: DescriptionContext) -> str:
    intro = f"{ctx.display_name} — монофільна волосінь для стабільної амортизації ривків і точного контролю оснастки."
    usage = "Рекомендовано для поплавкової, фідерної та універсальної ловлі, де важливі надійність вузлів і рівномірна подача."
    return build_standard_description(ctx, intro, usage, ["Тип", "Призначення", "Діаметр", "Розривне навантаження"])
