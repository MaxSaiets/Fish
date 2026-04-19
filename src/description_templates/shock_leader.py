from __future__ import annotations

from .base import DescriptionContext, build_standard_description


def build_description(ctx: DescriptionContext) -> str:
    intro = f"{ctx.display_name} — шок-лідер для безпечних силових закидань і захисту монтажу на старті."
    usage = "Використовується у фідерній та короповій риболовлі для зменшення ризику обриву при піковому навантаженні."
    return build_standard_description(ctx, intro, usage, ["Тип", "Матеріал", "Діаметр", "Розривне навантаження"])
