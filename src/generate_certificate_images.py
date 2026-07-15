# -*- coding: utf-8 -*-
"""
Генерує прості брендовані зображення для "порожніх" (без фото) товарів-
сертифікатів у категорії "Подарункові сертифікати" - без завантаження
зовнішніх файлів, локально через Pillow, у кольорах сайту (темно-синій
хедер #10192b, білий текст, помаранчевий акцент #FF6A1A).

  python src/generate_certificate_images.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(r"D:\FISH\fish-sync")
OUT_DIR = ROOT / "public" / "certificate-images"

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

W, H = 1200, 800
NAVY_DARK = (14, 22, 38)
NAVY_LIGHT = (24, 38, 63)
ORANGE = (255, 106, 26)
WHITE = (255, 255, 255)
MUTED = (150, 165, 190)

FONT_DIR = Path(r"C:\Windows\Fonts")

DENOMINATIONS = [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000]


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size)


def draw_certificate(amount: int) -> Image.Image:
    img = Image.new("RGB", (W, H), NAVY_DARK)
    draw = ImageDraw.Draw(img)

    # diagonal gradient-ish band
    for y in range(H):
        t = y / H
        r = int(NAVY_DARK[0] + (NAVY_LIGHT[0] - NAVY_DARK[0]) * t)
        g = int(NAVY_DARK[1] + (NAVY_LIGHT[1] - NAVY_DARK[1]) * t)
        b = int(NAVY_DARK[2] + (NAVY_LIGHT[2] - NAVY_DARK[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    margin = 48
    draw.rectangle([margin, margin, W - margin, H - margin], outline=ORANGE, width=4)
    draw.rectangle([margin + 14, margin + 14, W - margin - 14, H - margin - 14], outline=(70, 85, 110), width=1)

    f_brand = font("segoeuib.ttf", 40)
    f_label = font("segoeui.ttf", 34)
    f_amount = font("arialbd.ttf", 150)
    f_currency = font("segoeuib.ttf", 48)
    f_footer = font("segoeui.ttf", 26)

    brand = "ВСЕ ДЛЯ РИБАЛКИ"
    bbox = draw.textbbox((0, 0), brand, font=f_brand)
    draw.text(((W - (bbox[2] - bbox[0])) / 2, 110), brand, font=f_brand, fill=WHITE)

    draw.line([(W / 2 - 60, 175), (W / 2 + 60, 175)], fill=ORANGE, width=3)

    label = "ПОДАРУНКОВИЙ СЕРТИФІКАТ"
    bbox = draw.textbbox((0, 0), label, font=f_label)
    draw.text(((W - (bbox[2] - bbox[0])) / 2, 220), label, font=f_label, fill=MUTED)

    amount_text = f"{amount:,}".replace(",", " ")
    bbox = draw.textbbox((0, 0), amount_text, font=f_amount)
    amount_w = bbox[2] - bbox[0]
    curr_text = "ГРН"
    cbbox = draw.textbbox((0, 0), curr_text, font=f_currency)
    curr_w = cbbox[2] - cbbox[0]
    total_w = amount_w + 20 + curr_w
    start_x = (W - total_w) / 2
    draw.text((start_x, 340), amount_text, font=f_amount, fill=ORANGE)
    draw.text((start_x + amount_w + 20, 460), curr_text, font=f_currency, fill=WHITE)

    footer = "Дійсний на будь-які товари магазину · vsedliarybalky.com.ua"
    fbbox = draw.textbbox((0, 0), footer, font=f_footer)
    draw.text(((W - (fbbox[2] - fbbox[0])) / 2, H - 110), footer, font=f_footer, fill=MUTED)

    return img


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for amount in DENOMINATIONS:
        img = draw_certificate(amount)
        path = OUT_DIR / f"certificate_{amount}.jpg"
        img.save(path, "JPEG", quality=92)
        print(f"  {path.name}", flush=True)
    print(f"\nГотово: {len(DENOMINATIONS)} зображень у {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
