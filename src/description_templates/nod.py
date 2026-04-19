from __future__ import annotations

from .base import DescriptionContext, build_standard_description


def build_description(ctx: DescriptionContext) -> str:
    intro = f"{ctx.display_name} — кивок для чутливої індикації клювання на делікатних оснастках."
    usage = "Працює для зимової та міжсезонної ловлі, коли важливі точна сигналізація та контроль гри приманки."
    return build_standard_description(ctx, intro, usage, ["Тип", "Матеріал", "Сезон", "Довжина"])
