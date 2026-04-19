from __future__ import annotations

from .base import DescriptionContext, build_standard_description


def build_description(ctx: DescriptionContext) -> str:
    intro = f"{ctx.display_name} — рибальська насадка для точкового підбору аромату та презентації приманки."
    usage = "Підійде для коропової та фідерної риболовлі, коли потрібно швидко підібрати смак, фракцію або розмір під умови водойми."
    return build_standard_description(ctx, intro, usage, ["Тип насадки", "Тип суміші", "Плавучість", "Аромат", "Об'єм", "Вага"])
