# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`bwm_logistics` is a **Frappe v16 app on ERPNext** (Python ≥3.14) being built into a SaaS
logistics platform: import/export **container tracking with per-customer consolidation**,
courier/last-mile delivery, a **customer portal** with online payments, and a public
marketing site. The requirements live in **`docs/PRD.md`** (roadmap phases P0–P3) with
market research in `docs/market-research.md` — read the PRD before adding features.

Two halves:

- **`bwm_logistics/`** — the Frappe backend app (Python): `api/` (whitelisted endpoints),
  `www/` (public landing + SPA host page), `install.py` (roles), `hooks.py`. DocTypes
  (Container, Shipment, Tracking Event…) arrive in P1 per the PRD.
- **`frontend/`** — one **Vue 3.5 + TypeScript SPA** serving two route trees: the staff
  **operator app** at `/` and the **customer portal** under `/portal`. Mounted at the
  `/logistics` URL. Design and architecture are deliberately copied from the sibling
  `ex_beauty` app, rebranded **gold/black/white**.

## Critical context: this app lives inside a Frappe bench

The repo is one app inside a bench at `fb-16-6/` (`apps/bwm_logistics/`); the dev site is
`local16.6`. `bench` commands run from the **bench root**, not this app dir. The sibling
app **`ex_beauty`** (`apps/ex_beauty`) is the reference implementation — when unsure how a
frontend/backend pattern should look, check how ex_beauty does it. The **frappe/payments**
app provides the payment-gateway framework (PRD §4.8).

## Commands

Frontend — from the repo root (wrappers) or inside `frontend/`:

```bash
yarn dev        # Vite dev server on :8080, proxies API calls to Frappe on :8000
yarn build      # builds into bwm_logistics/public/dist/main (manifest-based)
yarn typecheck  # vue-tsc --noEmit
yarn shots      # Playwright UI audit — see below (needs a running bench)
```

**`yarn shots`** (from `frontend/`) drives the built SPA with Playwright and
writes PNGs to `frontend/tests/__shots__/` at phone/tablet/desktop widths. It
is a design-regression harness, not a unit runner:

- `screenshots.spec.ts` — every route against the live site (empty states).
- `populated.spec.ts` — the same list pages with `tests/fixtures.ts` stubbing
  `/api/method/*`, so long names and full tables are exercised **without
  writing a row to the database**. Fails on console errors and on any element
  overflowing a 390px viewport outside a deliberate scroller.
- `shell.spec.ts` — the shell contract (menu drawer, logo right, four bottom
  tabs, `/scan` gone).

Point it elsewhere with `BWM_BASE_URL` / `BWM_USER` / `BWM_PWD`; it defaults to
`http://localhost:8004` and a dev staff login. Build first — it tests the
compiled bundle, not the dev server.

Backend — from the **bench root** (`fb-16-6/`):

```bash
bench --site local16.6 migrate          # also re-runs install.py role setup (after_migrate)
bench --site local16.6 run-tests --app bwm_logistics
bench build --app bwm_logistics         # full asset build via Frappe
```

## Client opening data (JM Containers)

The client's live stock arrives as a working Excel. It reaches their site
**through the repo**, not by anyone copying a spreadsheet onto a server:

1. `import_jm_excel.extract` parses the workbook (sheets `Stock Tracker` and
   `Distribution`) and freezes it into **`bwm_logistics/data/jm_containers_opening.json`**,
   which is committed — a reviewable diff, and no openpyxl needed on the server.
2. The patch `bwm_logistics.patches.v1_0.import_client_opening_data`
   (`patches.txt`, `post_model_sync`) loads that file, so `bench migrate` after
   a deploy brings the site up with real containers, trading shipments,
   tracking events and distribution entries under the single **Accra** branch.

To refresh from a newer spreadsheet:

```bash
bench --site <site> execute bwm_logistics.import_jm_excel.extract \
    --kwargs "{'path': '/path/to/logistics excel data.xlsx'}"
git add bwm_logistics/data/jm_containers_opening.json   # commit + push, then migrate on the site
```

Both the extract and the load are idempotent — `load()` skips containers whose
`container_no` + `bl_no` already exist and distribution rows that already
match, so re-running after a restore or a data fix is safe. A failed load is
logged and does **not** block migrate; re-run it with
`bench --site <site> execute bwm_logistics.import_jm_excel.load_opening`.

Note: the .xlsx itself stays out of git (`*.xlsx` is gitignored) but the
extracted JSON does carry real container/BL numbers, customer names and
quantities — keep the repo private.

Lint / format: `pre-commit run --all-files` (ruff + ruff-format for Python — tab
indentation, line length 110; prettier + eslint for JS/Vue).

## How the SPA reaches the browser

1. `frontend/` builds with `manifest: true` into `bwm_logistics/public/dist/main/`
   (base `/assets/bwm_logistics/dist/main/`).
2. **`www/logistics.py`** reads `.vite/manifest.json` to resolve the hashed entry JS/CSS —
   no copy-html step; rebuilds never break the host page. It injects `window.csrf_token`
   and `window.frappe.boot` (full bootinfo) into `www/logistics.html`.
3. `hooks.py` `website_route_rules` maps `/logistics/<path>` → the `logistics` page so
   deep links reach the SPA; the Vue router uses history base `/logistics`.
4. The public landing page is **`www/home.html`** (self-contained Jinja + inline CSS,
   no Tailwind build) and `hooks.py` sets `home_page = "home"`.

## Auth, roles & access control (the architecture to preserve)

- Roles are created idempotently in `install.py` (`after_install` + `after_migrate`):
  `Logistics Manager / Operations / Accounts / Driver` (staff) and `Logistics Customer`
  (portal-only website users).
- **`api/access.py`** is the access layer: a static `ROLE_PAGES` map (P0) drives
  `my_permissions` (page→perm map consumed by the SPA session store) and
  `login_destinations` (staff → operator app, customer → `/logistics/portal`,
  System Managers → Desk chooser). **Page keys must match Vue route names.**
- `api/_perm.py` holds `require(*roles)` and `require_customer()` — every whitelisted
  endpoint calls one of these; the frontend map is UX only, never the security gate.
  Portal endpoints must scope queries by `current_customer()` (Contact→Customer link).
- Frontend: `stores/session.ts` reads server-injected boot, `loadAccess()` →
  `canSee(key)` / `can(page, action)`; the router guard redirects denied navigations to
  the first allowed page; `App.vue` renders Login for guests (no route chunk wasted).

## Frontend conventions (copied from ex_beauty — keep them)

- Tailwind + shadcn-vue style: `cn()` (`lib/utils.ts`), CVA-style variant maps in
  `ui/` primitives, reka-ui for headless primitives, lucide-vue-next icons, Pinia.
- **No frappe-ui / doppio** — the API client is the ~100-line `lib/frappe.ts` `call()`
  (CSRF header, `_server_messages` unwrapping, 401 → reload `/logistics`).
- Brand tokens (`tailwind.config.ts`): `brand` = gold ramp (600 `#b8860b` = primary CTA),
  `coal` = near-black bar scale (900 `#0f0f10`). CSS vars in `src/style.css`
  (`--primary: 43 89% 38%`). **Gold is never body text on white** — CTAs, active states,
  tints only. Cards settle at `rounded-2xl` with `p-4 sm:p-6`; shadows
  `xs/card/pop/modal`, system-ui font stack, `tabular-nums` for figures.
- Shared utilities in `style.css`: `.label-caps`, and `.chip-row` / `.chip` /
  `.chip-off` / `.chip-on` / `.chip-seg-on` for filter and segment strips — the
  row bleeds and scrolls sideways on a phone instead of clipping.
- Shared primitives: **`ui/PageHeader.vue`** (title + optional sub-line, actions
  drop to their own row under `sm`) and **`ui/StatCard.vue`** (figure + label).
  Pages should not hand-roll either.
- **No decorative icons beside figures.** A stat tile is a number and its label;
  icons are for controls that need them (menu, close, buttons). This is a
  deliberate correction — the dashboard used to carry a coloured glyph per tile.
- **`ui/DataTable.vue` renders twice**: a table from `md` up, one stacked card
  per row below it, sharing the same `#cell-<key>` slots. Columns declare
  `primary` (card headline), `trailing` (pinned top-right), `mobileHidden` and
  `nowrap`. Never add a `min-w-[…]` table that a phone has to scroll.
- Shell: `AppShell.vue` is a single h-14 coal-900 top bar — **menu button left**
  (opens the one nav drawer, at every breakpoint), everyday tabs centre on
  desktop, **logo hard right**. No avatar menu, no Apps launcher, no "Switch to
  Desk"; Log out lives at the foot of the drawer. Mobile gets four plain bottom
  tabs — no raised action and no "More". Pages are lazy-loaded and route names
  double as access keys.

## Watch out for

- **`ex_beauty` may be copied from; `cargo_management` (AgileShift) must NOT be** — it's
  AGPLv3 and this app is MIT. Patterns only.
- ERPNext's `Shipment` doctype is deliberately not reused (parcel-carrier model); the
  PRD specifies custom Container/Shipment doctypes. `Delivery Trip`/`Driver`/`Vehicle`
  are the intended reuse path for dispatch (P2).
- **The warehouse camera-scan feature was removed** (page, `/scan` route, the
  `scan` access-page key and the `html5-qrcode` dependency). Don't reintroduce it
  without asking — the PRD still describes FR-CON-6, but the product decision is
  that the app stays a lean read/track surface.
- Don't run `prettier` over `frontend/src` — the sources are hand-formatted with
  tabs and long class attributes per `.editorconfig` (max_line_length 99), and
  the pre-commit hook pins prettier v2.7.1 for `javascript, vue, scss` only.
  A stock prettier run reflows the whole tree at printWidth 80.
- Backend Python uses **tab indentation** (ruff-format enforced), matching Frappe.
- Branch is `main` (remote: github.com/buildwithmoi/bwm_logistics). CI spins up a
  fresh bench and runs `run-tests` on push/PR. Never add Co-Authored-By trailers to
  commits; commits are authored as buildwithmoi.
