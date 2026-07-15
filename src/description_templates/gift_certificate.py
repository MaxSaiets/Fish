from __future__ import annotations
from .base import DescriptionContext, build_standard_description


def build_description(ctx: DescriptionContext) -> str:
    intro = [
        f"{ctx.display_name} — безпрограшний подарунок для рибалки: сам обере саме те, "
        f"що потрібно, з понад семи тисяч позицій каталогу.",
        f"{ctx.display_name} — подарунок, який точно влучить: без ризику вгадати розмір, "
        f"клас снасті чи улюблений бренд — вибір лишається за рибалкою.",
    ]
    usage = [
        "Ідеально на день народження, свята чи відкриття сезону. Сертифікат діє на весь "
        "асортимент — снасті, прикормки, спорядження, одяг.",
        "Оформлення просте: обираєте номінал, а власник витрачає його на будь-які товари "
        "магазину зручним способом оплати.",
    ]
    return build_standard_description(ctx, intro, usage, ["Тип", "Призначення"])
