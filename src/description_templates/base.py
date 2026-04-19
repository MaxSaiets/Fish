from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DescriptionContext:
    family: str
    display_name: str
    brand: str
    type_word: str
    source_category: str
    name_raw: str
    common_params: dict[str, str]
    delta_params: dict[str, str]
    test_min: float | None
    test_max: float | None
    length_m: float | None
    action: str | None
    variant_count: int

    @classmethod
    def from_meta(cls, meta: dict) -> "DescriptionContext":
        return cls(
            family=str(meta.get("family") or "other"),
            display_name=str(meta.get("display_name") or meta.get("name_raw") or "Рибальський товар"),
            brand=str(meta.get("brand") or ""),
            type_word=str(meta.get("type_word") or "Рибальський товар"),
            source_category=str(meta.get("source_category") or ""),
            name_raw=str(meta.get("name_raw") or ""),
            common_params={str(k): str(v) for k, v in (meta.get("common_params") or {}).items() if str(v).strip()},
            delta_params={str(k): str(v) for k, v in (meta.get("delta_params") or {}).items() if str(v).strip()},
            test_min=meta.get("test_min"),
            test_max=meta.get("test_max"),
            length_m=meta.get("length_m"),
            action=str(meta.get("action") or "").strip() or None,
            variant_count=int(meta.get("variant_count") or 1),
        )

    def variant_marker(self) -> str:
        parts: list[str] = []
        if self.test_min is not None and self.test_max is not None:
            parts.append(f"тест {self.test_min:g}-{self.test_max:g} г")
        if self.length_m is not None:
            parts.append(f"довжина {self.length_m:g} м")
        if self.action:
            parts.append(f"лад {self.action}")
        for key in ("Діаметр", "Вага", "Об'єм", "Розмір", "Розривне навантаження"):
            value = self.delta_params.get(key)
            if value:
                parts.append(f"{key.lower()} {value}")
        return ", ".join(parts)


def build_standard_description(
    ctx: DescriptionContext,
    intro: str,
    usage: str,
    bullets: list[str],
) -> str:
    feature_items: list[str] = []
    for key in bullets:
        value = ctx.common_params.get(key) or ctx.delta_params.get(key)
        if value:
            feature_items.append(f"<li><strong>{key}:</strong> {value}</li>")
    if ctx.variant_marker():
        feature_items.append(f"<li><strong>Варіант:</strong> {ctx.variant_marker()}</li>")
    if ctx.variant_count > 1:
        feature_items.append(f"<li><strong>Кількість варіантів:</strong> {ctx.variant_count}</li>")
    if not feature_items:
        feature_items.append("<li>Підібрано для щоденної риболовлі у прісній воді.</li>")

    second = usage
    if ctx.source_category:
        second += f" Категорія каталогу: {ctx.source_category}."

    return (
        f"<p>{intro}</p>"
        f"<p>{second}</p>"
        f"<ul>{''.join(feature_items)}</ul>"
    )
