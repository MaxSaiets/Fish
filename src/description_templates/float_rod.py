from __future__ import annotations

from .base import DescriptionContext, build_standard_description


def build_description(ctx: DescriptionContext) -> str:
    intro = f"{ctx.display_name} — поплавкове вудилище для акуратної подачі оснастки та комфортної риболовлі."
    usage = "Оптимальне для ставків і тихої води, коли потрібна легкість, баланс і прогнозована робота снасті."
    return build_standard_description(ctx, intro, usage, ["Тип вудилища", "Довжина", "Стрій"])
