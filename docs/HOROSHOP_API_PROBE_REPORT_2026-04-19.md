# Horoshop API Probe Report (2026-04-19)

Environment:
- Base URL: `http://shop647643.horoshop.ua`
- Auth: `OK`
- Probe style: programmatic POST probe with token where required
- Scope: 485 endpoint patterns (`/api/{module}/{function}/`) + known explicit endpoints

## Confirmed Working Endpoints

- `POST /api/auth/` -> `OK`
- `POST /api/catalog/export/` -> `OK`
- `POST /api/catalog/import/` -> works, validates payload (`ERROR` when `products` empty)
- `POST /api/pages/export/` -> `OK`
- `POST /api/orders/get/` -> `EMPTY` (no orders found, endpoint exists)
- `POST /api/orders/update/` -> exists (`ERROR` when `orders` empty)
- `POST /api/orders/delete/` -> exists (`WARNING`/validation-based)
- `POST /api/settings/get/` -> `OK`
- `POST /api/currency/export/` -> `OK`
- `POST /api/delivery/export/` -> `OK`
- `POST /api/icons/export/` -> `OK`

## Confirmed Missing/Disabled Endpoints

- `POST /api/pages/import/` -> `UNDEFINED_FUNCTION`
- `POST /api/pages/delete/` -> `UNDEFINED_FUNCTION`
- `POST /api/catalog/delete/` -> `UNDEFINED_FUNCTION`
- `POST /api/catalog/remove/` -> `UNDEFINED_FUNCTION`
- `POST /api/catalog/clear/` -> `UNDEFINED_FUNCTION`
- `POST /api/catalog/list/` -> `UNDEFINED_FUNCTION`

## Key Limitation

The current API surface does not expose category tree creation/deletion methods (`pages/import` and delete variants are disabled).  
`catalog/import` also refuses products if target categories do not already exist.

Therefore:
- Full category reset + rebuild cannot be completed via API-only flow in this shop.
- Product updates/import into existing categories is supported.
