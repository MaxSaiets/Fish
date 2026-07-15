# Horoshop Customer Fix Plan 2026-06-05

## Done In This Iteration

- Renamed mobile/catalog menu item `Кормушки` to `Годівниці`.
- Kept `Спінінгові гачки` and `Коропові гачки`, and hid `Звичайні гачки` from menu and sitemap.
- Renamed `Інструменти PVA` to `Інструменти`.
- Renamed `Запчастини до вудилищ` to `Запчастини та аксесуари для вудок`.
- Standardized bait/pellet brand subcategories to English names:
  `Fanatik`, `Anvi`, `Real Fish`, `Interkril`, `Bounty`, `Boom`, `RPF`, `Puhach`.
- Updated delivery text: Ukrposhta is only for compact non-gabarit parcels after manager approval.
- Updated customer-facing schedule: Monday-Saturday 9:00-18:00, Sunday closed.
- Added order processing expectation: usually 3-4 days.
- Rebuilt Horoshop feed after category/brand/parameter normalization:
  `public/horoshop.xml`, 7942 products, 0 skipped.
- Added family-aware product normalization in `src/horoshop_catalog.py`:
  irrelevant filters are stripped per family, and risky parent categories are forced into correct branches.
- Added safe article filtering to `src/upload_horoshop_images.py` so image upload only touches articles that exist in `public/horoshop.xml`.
- Uploaded all prepared product photos from `public/mass-photo-utility` to Horoshop:
  7005/7005 valid article galleries uploaded with `cleanGallery`, 0 failed.
- Built the remaining-photo backlog:
  `data/missing_prepared_photo_articles_20260605.csv`,
  `data/missing_prepared_photo_summary_20260605.json`.
- Fixed `src/audit_live_product_media.py` to retry Horoshop anti-bot challenge pages instead of counting them as missing photos.

## Verification

- Live HTML no longer contains old menu labels:
  `Кормушки`, `Інструменти PVA`, `Запчастини до вудилищ`, `Звичайні гачки`,
  `Фанатік`, `Анві прикормка`, `Реал Фіш`, `Інтеркріл`,
  `Анві пелетс`, `Фанатік пелетс`, `Боунті`, `Бум`, `РПФ`, `Пугач`.
- Live HTML contains expected replacements:
  `Годівниці`, `Інструменти`, `Запчастини та аксесуари для вудок`,
  `Fanatik`, `Anvi`, `Real Fish`, `Interkril`, `Bounty`, `Boom`, `RPF`, `Puhach`.
- Contact page contains schedule text:
  `понеділок-субота 9:00-18:00`, `неділя`, `вихідний`.
- Delivery page contains `негабаритних` and `3-4 дні`.
- Product media upload reports:
  `data/mass_photo_upload_batch_0000_20260605.json`,
  `data/mass_photo_upload_batch_0500_20260605.json`,
  `data/mass_photo_upload_batch_1500_20260605.json`,
  `data/mass_photo_upload_batch_3000_20260605.json`,
  `data/mass_photo_upload_batch_4500_20260605.json`,
  `data/mass_photo_upload_batch_6000_20260605.json`.
- Live product media audit after upload:
  `data/live_product_media_audit_after_upload_full_retry_20260605.json`.
  Result: 7310/7311 sitemap URLs passed automatically, and the only timeout URL was manually rechecked and had a real gallery.
- Local prepared-photo coverage:
  7005 valid photo article groups, 937 products still need a prepared image source.
- Largest remaining missing-photo clusters:
  `всі` 209, `зернові` 174, `одяг та взуття` 118,
  `Запчастини та аксесуари для вудок` 47, `поп-ап` 45,
  `Anvi` 39, `Махові` 38, `Коропові` 28, `PVA матеріали` 26.
- Catalog data audit after normalization:
  `data/horoshop_param_distribution_report.json`, 45 families, 78 parent groups.

## Next Iteration Plan

1. Import the regenerated product feed into Horoshop.
   Use `public/horoshop.xml` and the documented Horoshop mapping flow.
   Do not run the old `src/horoshop_sync.py` directly for this, because it is based on the older `products.json`/`meta_store` path and does not fully use the canonical catalog fixes.

2. Re-audit live filters after import.
   Compare generated `data/horoshop_param_distribution_report.json` with live category filters and remove any remaining noisy values.

3. Finish the 937-product photo backlog.
   Start with the largest clusters: generic `всі`, `зернові`, `одяг та взуття`,
   rod spare parts, pop-ups, Anvi, махові and коропові rods.
   Prepare files into `public/mass-photo-utility` using the same `article@...jpg` naming and rerun `src/upload_horoshop_images.py`.

4. Recheck category previews and banners.
   Fix any category tiles that still use blank images, repeated images, text overlays, or irrelevant generic scenery.

5. Expand SEO content safely.
   Keep pages natural and useful, avoid repeated generic blocks, and make blog previews unique by topic.

6. Run final buyer-flow QA.
   Check desktop and mobile: catalog open, category navigation, product card, cart, login/register modal, delivery/payment pages and contact page.
