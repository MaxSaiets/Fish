from __future__ import annotations

from .base import DescriptionContext, build_standard_description


def build_description(ctx: DescriptionContext) -> str:
    intro = f"{ctx.display_name} — товар для риболовлі, підібраний для практичного використання на водоймі."
    usage = "Опис сформовано з доступних характеристик моделі, щоб покупець швидко оцінив сумісність та ключові параметри."
    return build_standard_description(ctx, intro, usage, ["Тип", "Матеріал", "Призначення", "Розмір", "Діаметр"])
