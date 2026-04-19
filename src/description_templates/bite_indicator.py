from __future__ import annotations

from .base import DescriptionContext, build_standard_description


def build_description(ctx: DescriptionContext) -> str:
    intro = f"{ctx.display_name} — сигналізатор клювання для своєчасного контролю оснастки вдень і вночі."
    usage = "Використовується у стаціонарній ловлі, коли потрібне швидке зчитування покльовки та зручна робота на підставках."
    return build_standard_description(ctx, intro, usage, ["Тип", "Підтип", "Довжина"])
