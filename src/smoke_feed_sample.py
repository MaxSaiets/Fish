from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from catalog_rules import parse_product
from render_facebook import render as render_facebook
from render_horoshop import render as render_horoshop
from render_rozetka import render as render_rozetka

ROOT = Path(r"D:\FISH\fish-sync")
PRODUCTS_JSON = ROOT / "data" / "products.json"
OUT_DIR = ROOT / "tmp" / "feed_smoke"


def pick_two_per_family(products: list[dict]) -> tuple[set[str], dict[str, int]]:
    selected: set[str] = set()
    per_family: dict[str, int] = defaultdict(int)
    for product in products:
        parsed = parse_product(product)
        if not parsed:
            continue
        family = parsed.family
        kod = str(product.get("kod") or "").strip()
        if not kod:
            continue
        if per_family[family] >= 2:
            continue
        selected.add(kod)
        per_family[family] += 1
    return selected, dict(sorted(per_family.items()))


def count_offers(xml_path: Path, offer_tag: str) -> int:
    root = ET.parse(xml_path).getroot()
    return len(root.findall(offer_tag))


def count_facebook_groups(xml_path: Path) -> Counter:
    root = ET.parse(xml_path).getroot()
    ns = {"g": "http://base.google.com/ns/1.0"}
    counter: Counter = Counter()
    for item in root.findall("./channel/item"):
        group = item.findtext("g:item_group_id", default="", namespaces=ns).strip()
        if group:
            counter[group] += 1
    return counter


def main() -> None:
    payload = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))
    products = payload["products"]

    selected_kods, per_family = pick_two_per_family(products)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    horoshop_xml = render_horoshop(out_xml=OUT_DIR / "horoshop_sample.xml", product_filter=selected_kods)
    rozetka_xml = render_rozetka(out_xml=OUT_DIR / "rozetka_sample.xml", product_filter=selected_kods)
    facebook_xml = render_facebook(out_xml=OUT_DIR / "facebook_sample.xml", product_filter=selected_kods)

    hs_offers = count_offers(horoshop_xml, "./shop/offers/offer")
    rz_offers = count_offers(rozetka_xml, "./shop/offers/offer")
    fb_items = count_offers(facebook_xml, "./channel/item")
    fb_groups = count_facebook_groups(facebook_xml)

    print("SMOKE FEED REPORT")
    print(f"families: {per_family}")
    print(f"selected_kods: {len(selected_kods)}")
    print(f"horoshop_offers: {hs_offers}")
    print(f"rozetka_offers: {rz_offers}")
    print(f"facebook_items: {fb_items}")
    print(f"facebook_grouped_items: {sum(v for v in fb_groups.values() if v > 1)}")
    print(f"output_dir: {OUT_DIR}")


if __name__ == "__main__":
    main()
