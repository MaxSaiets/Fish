from __future__ import annotations

import base64
import json
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(r"D:\FISH")
OUT_CSS = ROOT / "brand_override_live.css"
SITE_ASSETS_REPORT = ROOT / "fish-sync" / "data" / "horoshop_site_assets_report.json"
CATEGORY_VISUALS_REPORT = ROOT / "fish-sync" / "data" / "horoshop_category_visuals_report.json"
SOURCE_LOGO = Path(r"C:\Users\sayet\Downloads\Telegram Desktop\лого все для рибалки.svg")
SPECIAL_UPLOAD_REPORT = ROOT / "fish-sync" / "data" / "horoshop_special_placeholder_upload_report.json"
LIVE_MAP_CACHE = ROOT / "fish-sync" / "data" / "live_missing_article_map.json"
GENERATED_IMAGES_ROOT = ROOT / "fish-sync" / "public" / "generated-product-images"


def svg_data_uri(svg: str) -> str:
    payload = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f'url("data:image/svg+xml;base64,{payload}")'


def card_svg(title: str, lines: list[str], accent: str, badge: str) -> str:
    lines_svg = "".join(
        f'<text x="28" y="{220 + i * 24}" fill="#D7E2EE" font-size="18" font-family="Arial, Helvetica, sans-serif">{line}</text>'
        for i, line in enumerate(lines[:3])
    )
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 400">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#11283A"/>
      <stop offset="100%" stop-color="#081521"/>
    </linearGradient>
    <linearGradient id="glow" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="#F5B44A" stop-opacity="0.75"/>
    </linearGradient>
  </defs>
  <rect width="600" height="400" rx="22" fill="url(#bg)"/>
  <circle cx="528" cy="72" r="84" fill="url(#glow)" opacity="0.22"/>
  <circle cx="508" cy="322" r="110" fill="{accent}" opacity="0.09"/>
  <rect x="0" y="0" width="600" height="400" rx="22" fill="none" stroke="rgba(255,255,255,0.12)"/>
  <path d="M0 0 L140 0 L84 56 L0 56 Z" fill="{accent}"/>
  <text x="22" y="35" fill="#FFFFFF" font-size="18" font-weight="700" font-family="Arial, Helvetica, sans-serif">{badge}</text>
  <text x="28" y="110" fill="#FFFFFF" font-size="40" font-weight="800" font-family="Arial, Helvetica, sans-serif">{title}</text>
  <rect x="28" y="134" width="92" height="6" rx="3" fill="{accent}"/>
  {lines_svg}
  <text x="28" y="348" fill="#9CB0C4" font-size="15" font-family="Arial, Helvetica, sans-serif">Vsedliarybalky • товари для риболовлі</text>
  <text x="470" y="344" text-anchor="end" fill="#FFFFFF" font-size="72" font-weight="800" opacity="0.08" font-family="Arial, Helvetica, sans-serif">{badge}</text>
</svg>
""".strip()


def banner_svg(title: str, subtitle: str, cta: str, accent: str, size: tuple[int, int], mode: str) -> str:
    w, h = size
    if mode == "hero":
        title_size = 56
        subtitle_size = 24
        cta_y = h - 68
    elif mode == "wide":
        title_size = 42
        subtitle_size = 22
        cta_y = h - 54
    else:
        title_size = 32
        subtitle_size = 17
        cta_y = h - 44
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">
  <defs>
    <linearGradient id="heroBg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0C1C2A"/>
      <stop offset="100%" stop-color="#17344A"/>
    </linearGradient>
    <linearGradient id="wave" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="#F7B955" stop-opacity="0.85"/>
    </linearGradient>
  </defs>
  <rect width="{w}" height="{h}" rx="24" fill="url(#heroBg)"/>
  <circle cx="{w - 110}" cy="72" r="112" fill="{accent}" opacity="0.18"/>
  <circle cx="{w - 240}" cy="{h - 20}" r="130" fill="#FFFFFF" opacity="0.06"/>
  <path d="M0 {h - 38} C {int(w*0.15)} {h - 56}, {int(w*0.35)} {h - 6}, {int(w*0.55)} {h - 26} S {int(w*0.88)} {h - 74}, {w} {h - 32} L {w} {h} L 0 {h} Z" fill="#0A1621" opacity="0.62"/>
  <path d="M0 {h - 56} C {int(w*0.18)} {h - 72}, {int(w*0.42)} {h - 18}, {int(w*0.64)} {h - 40} S {int(w*0.90)} {h - 82}, {w} {h - 44}" fill="none" stroke="url(#wave)" stroke-width="6" stroke-linecap="round" opacity="0.55"/>
  <text x="42" y="62" fill="#D97706" font-size="18" font-weight="700" font-family="Arial, Helvetica, sans-serif">VSEDLIARYBALKY</text>
  <text x="42" y="{92 if mode == 'hero' else 78}" fill="#FFFFFF" font-size="{title_size}" font-weight="800" font-family="Arial, Helvetica, sans-serif">{title}</text>
  <text x="42" y="{132 if mode == 'hero' else 108}" fill="#D9E4EF" font-size="{subtitle_size}" font-family="Arial, Helvetica, sans-serif">{subtitle}</text>
  <rect x="42" y="{cta_y - 26}" rx="14" ry="14" width="{max(170, min(280, len(cta) * 12))}" height="42" fill="{accent}"/>
  <text x="62" y="{cta_y}" fill="#FFFFFF" font-size="20" font-weight="700" font-family="Arial, Helvetica, sans-serif">{cta}</text>
  <text x="{w - 46}" y="{h - 26}" text-anchor="end" fill="#9FB4C8" font-size="16" font-family="Arial, Helvetica, sans-serif">Риболовні снасті • Хмельницький • доставка по Україні</text>
</svg>
""".strip()


CATEGORIES: list[dict[str, object]] = [
    {"slug": "/kherabuna/", "title": "Херабуна", "badge": "HE", "accent": "#D97706", "lines": ["вудилища махові", "готові оснастки", "тісто та аксесуари"]},
    {"slug": "/vudylyshcha/", "title": "Вудилища", "badge": "ROD", "accent": "#D97706", "lines": ["коропові", "фідерні", "спінінгові"]},
    {"slug": "/kotushky/", "title": "Котушки", "badge": "REEL", "accent": "#F59E0B", "lines": ["коропові", "фідерні", "аксесуари"]},
    {"slug": "/volosin-ta-shnury/", "title": "Волосінь та шнури", "badge": "LINE", "accent": "#FB923C", "lines": ["волосінь", "шнури", "флюорокарбон"]},
    {"slug": "/chokhly/", "title": "Чохли", "badge": "CASE", "accent": "#EAB308", "lines": ["чохли та тубуси", "сумки та чохли"]},
    {"slug": "/hachky/", "title": "Гачки", "badge": "HOOK", "accent": "#F97316", "lines": ["спінінгові", "коропові", "гачки для оснащення"]},
    {"slug": "/hotovi-montazhi/", "title": "Готові монтажі", "badge": "RIG", "accent": "#C2410C", "lines": ["оранж монтажі", "інші монтажі"]},
    {"slug": "/vse-dlia-montazhu/", "title": "Все для монтажу", "badge": "KIT", "accent": "#EA580C", "lines": ["вертлюги та кільця", "годівниці", "грузила"]},
    {"slug": "/syhnalizatory-kliuvannia/", "title": "Сигналізатори клювання", "badge": "BITE", "accent": "#D97706", "lines": ["механічні", "електронні", "свінгери"]},
    {"slug": "/nasadochni/", "title": "Насадочні", "badge": "BAIT", "accent": "#FB923C", "lines": ["бойли", "поп-ап", "діпи"]},
    {"slug": "/prykormka/", "title": "Прикормка", "badge": "MIX", "accent": "#F59E0B", "lines": ["fanatik", "anvi", "real fish"]},
    {"slug": "/peletsy/", "title": "Пелетси", "badge": "PEL", "accent": "#EAB308", "lines": ["bounty", "anvi", "fanatik"]},
    {"slug": "/likvidy-i-atraktanty/", "title": "Ліквіди і атрактанти", "badge": "BOOST", "accent": "#F97316", "lines": ["ліквіди", "дипи", "підсилювачі аромату"]},
    {"slug": "/vidra-sumky-ta-orhanaizery/", "title": "Відра сумки та органайзери", "badge": "BOX", "accent": "#D97706", "lines": ["відра", "сумки", "органайзери"]},
    {"slug": "/pidstavky-ta-trymachi/", "title": "Підставки та тримачі", "badge": "STAND", "accent": "#FB923C", "lines": ["род-поди", "триноги", "аксесуари"]},
    {"slug": "/pidsaky-sadky-kukany/", "title": "Підсаки Садки кукани", "badge": "NET", "accent": "#F59E0B", "lines": ["підсаки", "садки", "ручки та голови"]},
    {"slug": "/krisla-stiltsi-ta-stoly/", "title": "Крісла стільці та столи", "badge": "CAMP", "accent": "#EAB308", "lines": ["крісла", "стільці", "столи"]},
    {"slug": "/pva-materialy-ta-aksesuary/", "title": "PVA матеріали та аксесуари", "badge": "PVA", "accent": "#D97706", "lines": ["pva матеріали", "інструменти"]},
    {"slug": "/zymova-lovlia/", "title": "Зимова ловля", "badge": "ICE", "accent": "#60A5FA", "lines": ["жерлиці", "льодобури", "мормишки"]},
    {"slug": "/turyzm/", "title": "Туризм", "badge": "OUT", "accent": "#34D399", "lines": ["ліхтарі", "термоси", "плити та пальники"]},
    {"slug": "/prymanky/", "title": "Приманки", "badge": "LURE", "accent": "#A78BFA", "lines": ["балансири", "блешні", "воблери"]},
]


def generated_assets_css() -> str:
    hero = svg_data_uri(
        banner_svg(
            "Все для рибалки",
            "Снасті, коропове, фідер та оснащення в одному магазині",
            "Перейти до каталогу",
            "#D97706",
            (960, 432),
            "hero",
        )
    )
    small_1 = svg_data_uri(
        banner_svg(
            "Вудилища та котушки",
            "Коропові, фідерні та спінінгові моделі",
            "Дивитися добірку",
            "#F59E0B",
            (480, 216),
            "small",
        )
    )
    small_2 = svg_data_uri(
        banner_svg(
            "Пелетс, бойли, прикормка",
            "Насадочні та прикормочні серії для сезону",
            "Перейти до насадок",
            "#FB923C",
            (480, 216),
            "small",
        )
    )
    wide = svg_data_uri(
        banner_svg(
            "Швидка доставка по Україні",
            "Самовивіз у Хмельницькому • консультація по підбору снастей",
            "Зв'язатися з нами",
            "#D97706",
            (1440, 216),
            "wide",
        )
    )

    parts = [
        "",
        "/* --- Generated brand assets: banners + root categories --- */",
        ".banners--blockplus .banner-image, .banners--block .banner-image {overflow:hidden; position:relative;}",
        ".banners--blockplus .banner-img, .banners--block .banner-img {opacity:0 !important;}",
        ".banners--blockplus .banner-image, .banners--block .banner-image {background-size:cover; background-position:center; background-repeat:no-repeat;}",
        f".banners--blockplus .banners__col--2of3 .banners__slider-i:first-child .banner-image {{background-image:{hero};}}",
        f".banners--blockplus .banners__col--1of3 .banners__cell:nth-child(1) .banner-image {{background-image:{small_1};}}",
        f".banners--blockplus .banners__col--1of3 .banners__cell:nth-child(2) .banner-image {{background-image:{small_2};}}",
        f".banners--block .banners__slider-i:first-child .banner-image {{background-image:{wide};}}",
        ".categories-unit-image{position:relative; overflow:hidden; border-radius:16px; background-size:cover; background-position:center; background-repeat:no-repeat; box-shadow:0 10px 24px rgba(9,24,37,.12);}",
        ".categories-unit-img.noPhoto{display:none !important; opacity:0 !important;}",
    ]
    for item in CATEGORIES:
        slug = item["slug"]
        css_slug = slug.replace('"', '\\"')
        image = svg_data_uri(card_svg(item["title"], item["lines"], item["accent"], item["badge"]))
        parts.append(f'.categories-unit-w > a[href="{css_slug}"] .categories-unit-image{{background-image:{image};}}')
    return "\n".join(parts)


def site_uploaded_assets_css() -> str:
    if not SITE_ASSETS_REPORT.exists():
        return ""

    report = json.loads(SITE_ASSETS_REPORT.read_text(encoding="utf-8"))
    uploads = report.get("uploads") or {}
    urls = {
        key: str(value.get("uri") or "").strip()
        for key, value in uploads.items()
        if isinstance(value, dict) and str(value.get("uri") or "").strip()
    }
    if not urls:
        return ""

    def css_url(key: str) -> str:
        value = urls.get(key, "")
        return f'url("{value}")' if value.startswith("http") else ""

    logo_png = css_url("logo_tight_png")
    logo_css = ""
    if not logo_png and SOURCE_LOGO.exists():
        logo_css = svg_data_uri(SOURCE_LOGO.read_text(encoding="utf-8"))

    parts = ["", "/* --- Uploaded real brand assets: logo --- */"]
    logo_image = logo_png or logo_css
    if logo_image:
        parts.extend(
            [
                ".header__logo,.footer__logo{background-repeat:no-repeat!important;background-position:center center!important;background-size:contain!important;}",
                f".header__logo,.footer__logo{{background-image:{logo_image}!important;}}",
                ".header-logo-img,.footer__logo-img{opacity:0!important;width:100%!important;max-width:none!important;}",
                ".header__logo{display:block!important;width:210px!important;min-width:210px!important;max-width:210px!important;height:70px!important;min-height:70px!important;overflow:visible!important;flex:0 0 210px!important;margin:0 18px 0 0!important;}",
                ".footer__logo{display:block!important;width:250px!important;min-width:250px!important;max-width:250px!important;height:82px!important;min-height:82px!important;overflow:visible!important;}",
                "@media (max-width:767px){.header__logo{width:150px!important;min-width:150px!important;max-width:150px!important;height:48px!important;min-height:48px!important;flex-basis:150px!important;margin-right:10px!important;}.footer__logo{width:190px!important;min-width:190px!important;max-width:190px!important;height:62px!important;min-height:62px!important;}}",
            ]
        )
    parts.extend(
        [
            ".frontInfo-content .text strong,.frontInfo-content h1,.frontInfo-content h2{color:var(--brand-header)!important;}",
            ".frontInfo-content a{color:var(--brand-accent)!important;}",
        ]
    )
    return "\n".join(parts)


def homepage_redesign_css() -> str:
    if not SITE_ASSETS_REPORT.exists():
        return ""

    report = json.loads(SITE_ASSETS_REPORT.read_text(encoding="utf-8"))
    uploads = report.get("uploads") or {}

    def css_url(key: str) -> str:
        value = uploads.get(key) if isinstance(uploads, dict) else None
        if not isinstance(value, dict):
            return ""
        url = str(value.get("uri") or "").strip()
        if not url.startswith("http"):
            return ""
        separator = "&" if "?" in url else "?"
        return f'url("{url}{separator}v=20260608-home-carp-hero")'

    carp_sets = css_url("carp_sets")
    veteran_500 = css_url("veteran_500")
    veteran_1000 = css_url("veteran_1000")
    veteran_1500 = css_url("veteran_1500")
    veteran_2000 = css_url("veteran_2000")

    parts = [
        "",
        "/* --- Homepage blockplus: hero 2/3 + side promo column 1/3 (banners 21/22 enabled 2026-06-10) --- */",
        "html body .banners--blockplus{height:auto!important;min-height:0!important;margin:14px auto 34px!important;padding:0 24px!important;overflow:visible!important;background:#FFFFFF!important;}",
        # висота підігнана під пропорцію hero-зображення 2.5:1 (2200x880), щоб cover не різав текст
        "html body .banners--blockplus .banners__container{display:block!important;width:100%!important;max-width:1440px!important;height:clamp(160px,40vw,420px)!important;min-height:160px!important;margin:0 auto!important;padding:0!important;gap:0!important;overflow:visible!important;position:relative!important;}",
        "@media (min-width:992px){html body .banners--blockplus .banners__container{height:clamp(240px,26.4vw,380px)!important;min-height:240px!important;}}",
        # перебиває старі min-height:430px (специфічність html body + 3 класи)
        "html body .banners--blockplus .banners__col--2of3 .banner-image{height:100%!important;min-height:0!important;max-height:100%!important;}",
        "html body .banners--blockplus .banners__col--1of3 .banner-image{height:100%!important;min-height:0!important;max-height:100%!important;}",
        "html body .banners--blockplus .banners__grid{display:grid!important;grid-template-columns:minmax(0,2fr) minmax(300px,1fr)!important;gap:16px!important;align-items:stretch!important;position:absolute!important;inset:0!important;width:100%!important;max-width:100%!important;height:100%!important;min-height:0!important;margin:0!important;padding:0!important;float:none!important;}",
        "html body .banners--blockplus .banners__col{height:100%!important;max-height:100%!important;width:100%!important;max-width:100%!important;flex:none!important;margin:0!important;padding:0!important;float:none!important;position:static!important;}",
        "html body .banners--blockplus .banners__col--2of3{display:block!important;}",
        "html body .banners--blockplus .banners__col--1of3{display:grid!important;visibility:visible!important;grid-template-rows:1fr 1fr!important;gap:16px!important;}",
        # бічні комірки показують реальні <img> банерів 21/22 (глобальне ховання banner-img не діє тут)
        "html body .banners--blockplus .banners__col--1of3 .banner-img,html body .banners--blockplus .banners__col--1of3 img.banner-img{display:block!important;opacity:1!important;visibility:visible!important;width:100%!important;height:100%!important;object-fit:cover!important;border-radius:18px!important;}",
        "html body .banners--blockplus .banners__col--1of3 .banner-image{background-color:#0C1C2A!important;border-radius:18px!important;overflow:hidden!important;}",
        "html body .banners--blockplus .banners__slider,html body .banners--blockplus .banners__slider-list,html body .banners--blockplus .banners__slider-wrapper,html body .banners--blockplus .banners__slider-i,html body .banners--blockplus .banners__item,html body .banners--blockplus .banner{display:block!important;width:100%!important;max-width:100%!important;height:100%!important;min-height:0!important;margin:0!important;padding:0!important;float:none!important;position:relative!important;left:auto!important;right:auto!important;transform:none!important;}",
        "html body .banners--blockplus .banners__cell{height:100%!important;margin:0!important;padding:0!important;}",
        "html body .banners--blockplus .banner-image{width:100%!important;height:100%!important;min-height:0!important;aspect-ratio:auto!important;border-radius:22px!important;background-color:#0C1C2A!important;background-size:cover!important;background-position:center!important;background-repeat:no-repeat!important;box-shadow:0 24px 64px rgba(12,28,42,.18)!important;border:1px solid rgba(12,28,42,.08)!important;}",
        "html body .banners--blockplus .banner-title,html body .banners--blockplus .banner-description,html body .banners--blockplus .banner-btn,html body .banners--blockplus .btn{display:none!important;}",
        "html body .banners--blockplus .banner-image::before{content:\"\";position:absolute;inset:0;border-radius:22px;box-shadow:inset 0 0 0 1px rgba(255,255,255,.24);pointer-events:none;}",
        "html body .frontAdvantages{max-width:1440px!important;margin:0 auto 34px!important;padding:0 24px!important;background:#FFFFFF!important;}",
        "html body .frontAdvantages .frontAdvantages-i,html body .frontAdvantages .frontAdvantages__inner{background:#FFFFFF!important;border:1px solid rgba(12,28,42,.10)!important;border-radius:20px!important;box-shadow:0 18px 44px rgba(12,28,42,.08)!important;overflow:hidden!important;}",
        "html body .frontInfo{background:linear-gradient(180deg,#F8FBFD 0%,#FFFFFF 100%)!important;padding-top:28px!important;}",
        "html body .banners--block{display:none!important;visibility:hidden!important;height:0!important;min-height:0!important;margin:0!important;padding:0!important;overflow:hidden!important;}",
        "@media (max-width:991px){html body .banners--blockplus .banners__grid{display:block!important;}html body .banners--blockplus .banners__col--1of3{display:none!important;visibility:hidden!important;}}",
        "@media (max-width:767px){html body .banners--blockplus{padding:0 12px!important;margin-top:10px!important;margin-bottom:22px!important;}html body .banners--blockplus .banners__container{height:auto!important;aspect-ratio:2.5/1!important;min-height:120px!important;}html body .banners--blockplus .banners__grid{display:block!important;}html body .banners--blockplus .banners__col--2of3{height:100%!important;}html body .banners--blockplus .banner-image{border-radius:16px!important;background-position:center!important;}html body .frontAdvantages{padding:0 12px!important;margin-bottom:22px!important;}}",
    ]
    if carp_sets:
        parts.append(
            f"html body .banners--blockplus .banners__col--2of3 .banners__slider-i:first-child .banner-image,html body .banners--blockplus .banners__col--2of3 .banner-image{{background-image:{carp_sets}!important;}}"
        )
    promo_images = [
        ("veteran_500", veteran_500),
        ("veteran_1000", veteran_1000),
        ("veteran_1500", veteran_1500),
        ("veteran_2000", veteran_2000),
    ]
    for index, (_, image) in enumerate(promo_images, start=1):
        if not image:
            continue
        parts.append(
            f"html body .banners--block .banners__slider-i:nth-child({index}) .banner-image{{background-image:{image}!important;background-size:cover!important;background-position:center!important;}}"
        )
    return "\n".join(parts)


def category_visuals_css() -> str:
    if not CATEGORY_VISUALS_REPORT.exists():
        return ""

    report = json.loads(CATEGORY_VISUALS_REPORT.read_text(encoding="utf-8"))
    uploads = report.get("uploads") or {}
    category_map = report.get("category_map") or {}
    banner_map = report.get("banner_map") or {}

    def uploaded_url(key: str) -> str:
        value = uploads.get(key) if isinstance(uploads, dict) else None
        if not isinstance(value, dict):
            return ""
        return str(value.get("uri") or "").strip()

    def css_url(key: str) -> str:
        url = uploaded_url(key)
        if url.startswith("http"):
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}v=20260602-opera-fix"
        return f'url("{url}")' if url.startswith("http") else ""

    parts = [
        "",
        "/* --- Curated stock visuals: homepage banners + every category/subcategory --- */",
        ".banners--blockplus .banner-image::after,.banners--block .banner-image::after{content:\"\";position:absolute;inset:0;background:linear-gradient(90deg,rgba(12,28,42,.72),rgba(12,28,42,.16) 56%,rgba(12,28,42,.34));pointer-events:none;}",
        ".banners--blockplus .banner-title,.banners--block .banner-title,.banner-title{color:#fff!important;text-shadow:0 2px 14px rgba(0,0,0,.42);}",
        ".categories-unit-w > a .categories-unit-image{display:block!important;width:180px!important;height:164px!important;min-height:164px!important;border-radius:16px!important;background-color:transparent!important;background-size:cover!important;background-position:center!important;background-repeat:no-repeat!important;}",
        ".categories-unit-image::after{display:none!important;content:none!important;background:none!important;}",
        ".categories-unit-image .categories-unit-img.noPhoto{display:none!important;opacity:0!important;visibility:hidden!important;}",
        ".categories-unit-w:hover .categories-unit-image{transform:translateY(-2px);transition:transform .22s ease, box-shadow .22s ease;box-shadow:0 16px 34px rgba(9,24,37,.18);}",
    ]

    banner_selectors = {
        "home_hero": ".banners--blockplus .banners__col--2of3 .banners__slider-i:first-child .banner-image",
        # home_rods/home_bait прибрано 2026-06-10: бічні комірки тепер показують
        # реальні банери 21/22 (image_small), а не форсовані стокові фони.
        "home_wide": ".banners--block .banners__slider-i:first-child .banner-image",
    }
    for key, selector in banner_selectors.items():
        asset_key = banner_map.get(key, key)
        if key == "home_wide":
            asset_key = banner_map.get("home_hero", "home_hero")
        image = css_url(asset_key)
        if image:
            parts.append(f"{selector}{{background-image:{image}!important;background-size:cover!important;background-position:center!important;}}")

    for slug, asset_key in sorted(category_map.items()):
        if not isinstance(slug, str) or not isinstance(asset_key, str):
            continue
        image = css_url(asset_key)
        if not image:
            continue
        slug_css = slug.replace('"', '\\"')
        parts.append(
            f'.categories-unit-w > a[href="{slug_css}"] .categories-unit-image,'
            f'a[href="{slug_css}"] .categories-unit-image{{background-image:{image}!important;background-size:cover!important;background-position:center!important;}}'
        )
        parts.append(
            f'.categories-unit-w > a[href="{slug_css}"] .categories-unit-img,'
            f'a[href="{slug_css}"] .categories-unit-img{{opacity:0!important;}}'
        )
    return "\n".join(parts)


def storefront_render_repair_css() -> str:
    return """
/* --- Storefront render repair: catalog menu contrast + stable homepage banners --- */
.header .productsMenu-submenu,
.header .productsMenu-submenu *,
.header .productsMenu-tabs,
.header .productsMenu-tabs *,
.header .productsMenu-tabs-content,
.header .productsMenu-tabs-content *,
.header .productsMenu-tabs-switch,
.header .productsMenu-tabs-switch *{
  color:#0C1C2A!important;
  text-shadow:none!important;
}
.header .productsMenu-submenu{
  background:#FFFFFF!important;
  border:1px solid rgba(12,28,42,.08)!important;
  box-shadow:0 22px 52px rgba(12,28,42,.16)!important;
}
.header .productsMenu-tabs-content,
.header .productsMenu-tabs-switch,
.header .productsMenu-submenu-w{
  background:#FFFFFF!important;
}
.header .productsMenu-tabs-list__tab.__hover,
.header .productsMenu-tabs-list__tab:hover,
.header .productsMenu-tabs-list__link:hover,
.header .productsMenu-submenu-a:hover{
  background:#F3F7FB!important;
  color:#0C1C2A!important;
}
.header .productsMenu-submenu-a,
.header .productsMenu-submenu-t,
.header .productsMenu-tabs-list__link{
  color:#0C1C2A!important;
  opacity:1!important;
  visibility:visible!important;
}
.header .productsMenu-submenu-a:hover .productsMenu-submenu-t,
.header .productsMenu-tabs-list__link:hover{
  color:#D97706!important;
}
.banners--blockplus,
.banners--block,
.banners--blockplus .banners__slider,
.banners--block .banners__slider{
  display:block!important;
  visibility:visible!important;
  opacity:1!important;
}
.banners--blockplus .banner-image,
.banners--block .banner-image{
  display:flex!important;
  visibility:visible!important;
  opacity:1!important;
  overflow:hidden!important;
  position:relative!important;
  background-color:#0C1C2A!important;
  background-repeat:no-repeat!important;
  background-size:cover!important;
  background-position:center!important;
}
.banners--blockplus .banner-img,
.banners--block .banner-img,
.banners--blockplus img.banner-img,
.banners--block img.banner-img{
  display:none!important;
  opacity:0!important;
  visibility:hidden!important;
}
.banners--blockplus .banner-image::after,
.banners--block .banner-image::after{
  display:none!important;
  content:none!important;
  background:none!important;
}
.frontInfo,
.frontAdvantages,
.categories{
  background:#FFFFFF!important;
}
.categories-unit,
.categories-unit-w,
.categories-unit-info,
.categories-unit-content,
.categories-list,
.categories-grid,
.categories-container,
.categories .layout-wrap{
  background:#FFFFFF!important;
  background-image:none!important;
}
.categories-unit-w > a,
.categories-unit > a,
.categories-unit a:not(.btn){
  background:transparent!important;
  background-color:transparent!important;
  background-image:none!important;
}
.categories-unit *,
.categories-unit *::before,
.categories-unit *::after{
  background-color:transparent!important;
}
.categories-unit-image,
.categories-unit-w > a .categories-unit-image,
.categories-unit a .categories-unit-image{
  background-color:transparent!important;
}
.categories-unit-h,
.categories-unit-h *,
.categories-list,
.categories-list *{
  background:#FFFFFF!important;
  background-image:none!important;
}
.categories-unit .btn,
.categories-unit .btn *,
.categories-unit .btn-content{
  background:#D97706!important;
  background-image:none!important;
  color:#FFFFFF!important;
}
html body .categories.__bigIcons,
html body .categories.__bigIcons .layout-wrap,
html body .categories.__bigIcons .categories-container,
html body .categories.__bigIcons .categories-grid,
html body .categories.__bigIcons .categories-unit,
html body .categories.__bigIcons .categories-unit-w,
html body .categories.__bigIcons .categories-unit-h,
html body .categories.__bigIcons .categories-unit-h *,
html body .categories.__bigIcons .categories-list,
html body .categories.__bigIcons .categories-list *,
html body .categories.__bigIcons .a-link{
  background:#FFFFFF!important;
  background-color:#FFFFFF!important;
  background-image:none!important;
}
html body .categories.__bigIcons .categories-unit-image{
  background-color:transparent!important;
}
html body .categories.__bigIcons .btn,
html body .categories.__bigIcons .btn *,
html body .categories.__bigIcons .btn-content{
  background:#D97706!important;
  background-color:#D97706!important;
  color:#FFFFFF!important;
}
.categories-unit-w{
  box-shadow:none!important;
}
.banners--blockplus .banners__col--2of3 .banner-image{min-height:288px!important;}
.banners--blockplus .banners__col--1of3 .banner-image{min-height:139px!important;}
.banners--block .banner-image{min-height:144px!important;}
.banners--blockplus{
  margin:16px 0 28px!important;
  height:338px!important;
  min-height:338px!important;
  overflow:visible!important;
}
.banners--blockplus .banners__container{
  display:grid!important;
  grid-template-columns:minmax(0,2fr) minmax(280px,1fr)!important;
  gap:16px!important;
  align-items:stretch!important;
  width:calc(100% - 30px)!important;
  height:328px!important;
  min-height:328px!important;
  margin-left:15px!important;
  margin-right:15px!important;
  overflow:visible!important;
  position:relative!important;
}
.banners--blockplus .banners__col{
  width:auto!important;
  min-width:0!important;
  height:100%!important;
  max-height:100%!important;
  padding:0!important;
  margin:0!important;
  float:none!important;
  position:static!important;
}
.banners--blockplus .banners__col--1of3{
  display:grid!important;
  grid-template-rows:calc((100% - 12px) / 2) calc((100% - 12px) / 2)!important;
  gap:16px!important;
}
.banners--blockplus .banners__cell{
  height:auto!important;
  min-height:0!important;
  padding:0!important;
  margin:0!important;
  position:static!important;
}
.banners--blockplus .banner-image{
  width:100%!important;
  height:100%!important;
  min-height:0!important;
  max-height:100%!important;
  border-radius:8px!important;
}
.banners--blockplus .banners__col--2of3 .banner-image{
  height:100%!important;
  min-height:0!important;
}
.banners--blockplus .banners__col--1of3 .banner-image{
  height:100%!important;
  min-height:0!important;
}
.frontAdvantages{
  margin-top:0!important;
}
@media (min-width:1200px){
  .banners--blockplus .banners__col--2of3 .banner-image{min-height:430px!important;}
  .banners--blockplus .banners__col--1of3 .banner-image{min-height:207px!important;}
  .banners--block .banner-image{min-height:180px!important;}
}
@media (max-width:767px){
  .banners--blockplus .banners__container{
    display:grid!important;
    grid-template-columns:1fr!important;
    gap:12px!important;
  }
  .banners--blockplus .banners__col--1of3{
    display:grid!important;
    gap:12px!important;
    margin-top:0!important;
  }
  .banners--blockplus .banners__col--2of3 .banner-image,
  .banners--blockplus .banners__col--1of3 .banner-image,
  .banners--block .banner-image{min-height:190px!important;}
}
html body .banners--blockplus .banners__container{
  display:grid!important;
}
html body .banners--blockplus .banners__cell .banner-image{
  height:100%!important;
  min-height:0!important;
  max-height:100%!important;
}
""".strip()


def article_to_generated_path(article: str) -> Path:
    normalized = article.replace("\\", "/")
    return GENERATED_IMAGES_ROOT.joinpath(*normalized.split("/")) / "1.jpg"


def mobile_overflow_guard_css() -> str:
    return """
@media (max-width:767px){
  html,
  body{
    width:100%!important;
    max-width:100%!important;
    overflow-x:hidden!important;
  }
  .layout,
  .layout-wrap,
  .wrapper,
  .container,
  .main,
  .content,
  .site-content,
  .page,
  .page-container,
  .header,
  .header__container,
  .header__middle,
  .header__wrapper,
  .header__layout,
  .products-menu,
  .products-menu__container,
  .productsMenu,
  .productsMenu-tabs,
  .productsMenu-tabs-list,
  .productsMenu-submenu,
  .productsMenu-submenu-c,
  .frontInfo,
  .frontAdvantages,
  .categories,
  .categories-container,
  .categories-grid,
  .categories-list,
  .categories-content,
  .categories-block{
    min-width:0!important;
    width:100%!important;
    max-width:100%!important;
    box-sizing:border-box!important;
  }
  .categories,
  .categories-container,
  .categories-grid,
  .categories-list,
  .categories-content{
    display:grid!important;
    grid-template-columns:1fr!important;
    gap:18px!important;
    padding-left:12px!important;
    padding-right:12px!important;
    margin-left:0!important;
    margin-right:0!important;
  }
  .categories-unit,
  .categories-unit-w{
    min-width:0!important;
    width:100%!important;
    max-width:100%!important;
    margin:0 0 18px!important;
    padding:0!important;
    float:none!important;
    clear:both!important;
    position:relative!important;
    left:auto!important;
    right:auto!important;
    transform:none!important;
    box-sizing:border-box!important;
  }
  .categories-unit-w > a,
  .categories-unit > a{
    width:100%!important;
    max-width:100%!important;
    box-sizing:border-box!important;
  }
  .categories-unit-image,
  .categories-unit-w > a .categories-unit-image,
  .categories-unit a .categories-unit-image{
    width:100%!important;
    max-width:100%!important;
    height:180px!important;
    min-height:180px!important;
  }
  .header__column--right,
  .header__section .timetable,
  .header__column--right .basket-view,
  .header__column--right .basket{
    display:none!important;
    visibility:hidden!important;
  }
  .header__column--wide,
  .header__column--vertical{
    min-width:0!important;
    width:auto!important;
    max-width:calc(100% - 170px)!important;
    flex:1 1 auto!important;
    box-sizing:border-box!important;
  }
  .header .phones,
  .header .phones a{
    white-space:normal!important;
    overflow-wrap:anywhere!important;
  }
  .header .search,
  .header .search form{
    min-width:0!important;
    width:100%!important;
    max-width:100%!important;
    box-sizing:border-box!important;
  }
  .header .search{
    clear:both!important;
    margin:8px 0 0!important;
  }
  .header .search__input{
    width:100%!important;
    max-width:100%!important;
    box-sizing:border-box!important;
  }
  .header .search__button{
    right:0!important;
  }
  .frontBenefits,
  .frontBenefits-i,
  .frontBenefits-item,
  .frontBenefits-txt,
  .frontBenefits-txt-h{
    min-width:0!important;
    max-width:100%!important;
    width:100%!important;
    box-sizing:border-box!important;
    transform:none!important;
    left:auto!important;
    right:auto!important;
  }
  .footer,
  .footer__container,
  .footer__row,
  .footer__col,
  .footer__col-wrap,
  .footer__block,
  .footer__menu{
    min-width:0!important;
    max-width:100%!important;
    width:100%!important;
    box-sizing:border-box!important;
    margin-left:0!important;
    margin-right:0!important;
    float:none!important;
    transform:none!important;
    left:auto!important;
    right:auto!important;
  }
  .footer__row,
  .frontBenefits{
    display:block!important;
  }
  .footer__link,
  .footer a,
  .footer__contacts-item,
  .footer__contacts-item-link{
    white-space:normal!important;
    overflow-wrap:anywhere!important;
    word-break:break-word!important;
  }
}
""".strip()


def image_to_data_uri(path: Path) -> str:
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'url("data:image/jpeg;base64,{payload}")'


def special_product_overrides_css() -> str:
    if not SPECIAL_UPLOAD_REPORT.exists() or not LIVE_MAP_CACHE.exists():
        return ""

    report = json.loads(SPECIAL_UPLOAD_REPORT.read_text(encoding="utf-8"))
    live_map = json.loads(LIVE_MAP_CACHE.read_text(encoding="utf-8"))
    url_by_article = {
        str(item.get("article") or "").strip(): str(item.get("url") or "").strip()
        for item in live_map.get("items", [])
        if str(item.get("article") or "").strip() and str(item.get("url") or "").strip()
    }

    failed_articles = [
        str(item.get("article") or "").strip()
        for item in report.get("failed", [])
        if str(item.get("article") or "").strip()
    ]
    if not failed_articles:
        return ""

    parts = [
        "",
        "/* --- Fallback visuals for edge-case product articles not accepted by Horoshop image import --- */",
        ".product__section--gallery .gallery-link{background-position:center;background-repeat:no-repeat;background-size:contain;}",
    ]
    for article in failed_articles:
        product_url = url_by_article.get(article)
        image_path = article_to_generated_path(article)
        if not product_url or not image_path.exists():
            continue
        product_url = unquote(product_url)
        slug = product_url.replace("https://vsedliarybalky.com.ua", "")
        image_uri = image_to_data_uri(image_path)
        product_url_css = product_url.replace('"', '\\"')
        slug_css = slug.replace('"', '\\"')
        parts.append(
            f'html:has(link[rel="canonical"][href="{product_url_css}"]) .product__section--gallery .gallery-link{{'
            f'display:block;min-height:420px;width:100%;border-radius:18px;background-color:#FFFFFF;'
            f'background-image:{image_uri};}}'
        )
        parts.append(
            f'html:has(link[rel="canonical"][href="{product_url_css}"]) .product__section--gallery .gallery__photo-img.noPhoto{{display:none!important;}}'
        )
        parts.append(
            f'a.a-link[href="{slug_css}"]{{display:block;min-height:220px;border-radius:16px;background-color:#FFFFFF;'
            f'background-position:center;background-repeat:no-repeat;background-size:contain;background-image:{image_uri};}}'
        )
        parts.append(f'a.a-link[href="{slug_css}"] .noPhoto{{display:none!important;}}')
    return "\n".join(parts)


def base_css() -> str:
    return """
:root{
  --brand-header:#0C1C2A;
  --brand-accent:#D97706;
  --brand-text:#1E293B;
  --brand-muted:#94A3B8;
  --brand-light:#FFFFFF;
}
body{color:var(--brand-text)!important;}
.header,.header__middle,.header__bottom,.footer{
  background:var(--brand-header)!important;
  color:var(--brand-light)!important;
}
.header a,.header .phones,.header .phones a,.header .userbar__button,.header .userbar__button-text,.header .products-menu__button-text,.header .top-menu a,.header .search__button,.footer,.footer a,.footer__heading,.footer__copyright,.footer__address,.footer__contacts-item,.footer__contacts-item-link,.main-h,.footer__link{
  color:var(--brand-light)!important;
}
.header .userbar__button,.header .userbar__button-icon,.header .comparison-button,.header .favorites-button,.header .cart-button,.header .login-button,.header svg,.header .icon{
  color:#FFFFFF!important;
  fill:#FFFFFF!important;
  stroke:#FFFFFF!important;
}
.header .userbar__button:hover,.header .comparison-button:hover,.header .favorites-button:hover,.header .cart-button:hover,.header .login-button:hover{
  color:var(--brand-accent)!important;
  fill:var(--brand-accent)!important;
  stroke:var(--brand-accent)!important;
}
.header .userbar__button-text,.header .login-button,.header a[href*="login"],.header a[href*="profile"]{
  color:#FFFFFF!important;
}
.header .basket,
.header .basket *,
.header .basket__title,
.header .basket__contents,
.header .j-basket-title{
  color:#FFFFFF!important;
  fill:#FFFFFF!important;
  stroke:#FFFFFF!important;
}
.header__logo,.footer__logo{display:block!important;min-height:52px;}
.header-logo-img,.footer__logo-img{display:block!important;max-height:62px;width:auto!important;object-fit:contain;}
.btn.__special,.btn.__special .btn-content,.btn.__small,.btn.__small .btn-content,button.btn,.products-menu__button,.products-menu__button-text,.cart-btnOrder .btn,.search__button{
  background:var(--brand-accent)!important;
  border-color:var(--brand-accent)!important;
  color:var(--brand-light)!important;
}
.btn.__clear,.btn.__clear .btn-content{color:var(--brand-header)!important;}
.product-header__availability--out-of-stock,.catalogCard-status--out-of-stock,.availability--out-of-stock{color:var(--brand-muted)!important;}
.categories-unit-h .a-link{color:var(--brand-text)!important;font-weight:800;}
.categories-list a{color:#516274!important;}
.categories-list a:hover{color:var(--brand-accent)!important;}
.popup-header,
.login-header,
.compare-header,
.cart-header-b,
.popup-window,
.popup,
.login,
.registration,
.cart,
.cart-page{
  background:#FFFFFF!important;
  color:var(--brand-text)!important;
}
.popup-header *,
.login-header *,
.popup-window *,
.login *,
.registration *,
.cart *,
.cart-page *{
  color:inherit;
}
.login-tabs,
.login-tabs *,
.popup-tabs,
.popup-tabs *,
.tabs,
.tabs *{
  background:#FFFFFF!important;
  color:var(--brand-text)!important;
}
.login-tabs .is-active,
.popup-tabs .is-active,
.tabs .is-active,
.login-tabs .active,
.popup-tabs .active,
.tabs .active{
  background:#FFFFFF!important;
  color:var(--brand-header)!important;
}
.cart-header-b,
.cart-header-b *,
.cart-table th,
.cart-table thead,
.cart-products thead,
.cart-products th,
.cart-order thead,
.cart-order th{
  background:#FFFFFF!important;
  background-color:#FFFFFF!important;
  color:var(--brand-text)!important;
}
.frontAdvantages,.frontInfo{background:#F8FBFD!important;}
@media (max-width:767px){
  .header__logo,.footer__logo{min-height:42px;}
  .header-logo-img,.footer__logo-img{max-height:42px;}
}
@media (max-width:767px){
  html,
  body{
    width:100%!important;
    max-width:100%!important;
    overflow-x:hidden!important;
  }
  .layout,
  .layout-wrap,
  .wrapper,
  .container,
  .main,
  .content,
  .site-content,
  .page,
  .page-container,
  .header,
  .header__container,
  .header__middle,
  .header__wrapper,
  .header__layout,
  .products-menu,
  .products-menu__container,
  .productsMenu,
  .productsMenu-tabs,
  .productsMenu-tabs-list,
  .productsMenu-submenu,
  .productsMenu-submenu-c,
  .frontInfo,
  .frontAdvantages,
  .categories,
  .categories-container,
  .categories-grid,
  .categories-list,
  .categories-content,
  .categories-block{
    min-width:0!important;
    width:100%!important;
    max-width:100%!important;
    box-sizing:border-box!important;
  }
  .categories,
  .categories-container,
  .categories-grid,
  .categories-list,
  .categories-content{
    display:grid!important;
    grid-template-columns:1fr!important;
    gap:18px!important;
    padding-left:12px!important;
    padding-right:12px!important;
    margin-left:0!important;
    margin-right:0!important;
  }
  .categories-unit,
  .categories-unit-w{
    min-width:0!important;
    width:100%!important;
    max-width:100%!important;
    margin:0 0 18px!important;
    padding:0!important;
    float:none!important;
    clear:both!important;
    position:relative!important;
    left:auto!important;
    right:auto!important;
    transform:none!important;
    box-sizing:border-box!important;
  }
  .categories-unit-w > a,
  .categories-unit > a{
    width:100%!important;
    max-width:100%!important;
    box-sizing:border-box!important;
  }
  .categories-unit-image,
  .categories-unit-w > a .categories-unit-image,
  .categories-unit a .categories-unit-image{
    width:100%!important;
    max-width:100%!important;
    height:180px!important;
    min-height:180px!important;
  }
}
""".strip()


def main() -> None:
    final_css = (
        base_css()
        + "\n"
        + site_uploaded_assets_css()
        + "\n"
        + category_visuals_css()
        + "\n"
        + storefront_render_repair_css()
        + "\n"
        + homepage_redesign_css()
        + "\n"
        + mobile_overflow_guard_css()
        + "\n"
    )
    OUT_CSS.write_text(final_css, encoding="utf-8")
    print(f"Wrote {OUT_CSS} ({len(final_css)} chars)")


if __name__ == "__main__":
    main()
