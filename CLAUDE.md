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
  writing a row to the database**.
- `shell.spec.ts` — the shell contract (menu drawer, logo right, four bottom
  tabs, `/scan` gone).
- `create-flows.spec.ts` — every "New …" button lands on a real URL that
  survives reload and Back, and the dialogs that remain still fit a phone
  (dialog contents only exist once opened, so the route sweep never sees them).

**`tests/overflow.ts` is the mobile-fit check** and it is easy to get wrong.
The shell scrolls inside `<main>`, not the document, so
`documentElement.scrollWidth` never grows however far a field spills; and
because `main` is `overflow-y: auto` its *computed* `overflow-x` is `auto` too,
so "skip anything inside a scroller" skips the whole page. Measure `main`
itself. Both traps were live here and hid real overflow.

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

**`opening_repair.run()` is the deploy safety net, and it is on `after_migrate`
rather than only in a patch for a specific reason.**
`frappe.installer.install_app()` calls `set_all_patches_as_completed()` *before*
`after_install` runs, so a freshly installed site records every patch as done
without executing one — a patch therefore cannot heal a new server, which is
the deployment most likely to need it. The sweep runs on every migrate instead,
is idempotent, prints nothing when there is nothing to fix, and repairs:
missing opening data (the import is allowed to fail so it can never block an
upgrade — this is what notices), containers with no manifest, shipments still
naming their box only through the legacy single link, catalogue items left on
the `Both` fallback, and stale totals.

The catalogue needs ERPNext's Item Group tree and UOM list, which the **setup
wizard** creates — not `install-app`. On a provisioned-but-not-set-up server
`items.catalogue_blocker()` reports why, the import defers instead of throwing,
and the next migrate finishes the job. Run it by hand with
`bench --site <site> execute bwm_logistics.opening_repair.run`.

**Seeding happens once, and a wipe stays wiped.** `Logistics Settings.
opening_data_loaded` is set the first time the opening balance is accounted for
(by the install hook, or by the sweep finding it already there). While it is
set, `opening_repair` never seeds again — otherwise clearing the site to enter
records by hand would be undone by the next migrate, which is resurrection, not
repair. `reset_demo_data.run()` leaves the flag set for exactly that reason.
Untick it (or run `import_jm_excel.load_opening()`) to ask for the data back.

To start a site over instead of repairing it, that is a separate, deliberate act:
`reset_demo_data.run()` then, if you want the opening balance again, untick the
flag and migrate.

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
- **Creating a record is a page, not a dialog**, whenever it takes more than a
  handful of fields — containers, shipments, delivery runs, invoices, purchases
  all live at `/…/new` and are built from **`ui/FormPage.vue`** +
  **`ui/FormSection.vue`**. Dialogs stay for the small stuff: a customer, a
  driver, a payment, a milestone. A repeating line-item table is the tell that
  something wants a page. (Rate cards are the one repeating-table form still in
  a dialog.)
- **Record screens wear `ui/DetailHeader.vue`**: a labelled back control ("‹
  Shipments", 40px target — never a bare arrow in the margin), actions pinned
  **right**, then the title + status badges on their own row. Back calls
  `router.back()` when there's history to pop so the list keeps its scroll and
  filters, and falls back to the parent URL for a reloaded deep link.
- **Actions go bottom-right / top-right, at every width** — including on a
  phone. Full-width stacked buttons read as two equal choices and put Cancel
  under the thumb.
- **A status is changed by picking from a list, never by typing.** Shipments and
  containers both open `ui/Sheet.vue` — a bottom sheet on a phone, a centred
  dialog from `sm` — listing each milestone with the status it lands on.
  `api/shipments.milestone_options()` is the source; a free-text milestone box
  is unusable because the accepted values live in `MILESTONE_STATUS`.
- **Mobile is not desktop.** The PWA is treated as an app: `DataTable` renders
  cards vs a table, `Sheet` rises from the bottom vs centring, `DataList`
  stacks label/value rows vs two columns, and header actions collapse to icons.
  Don't "fix" these into one shared layout.
- Shared display primitives: **`ui/Badge.vue`** (the one pill — `StatusBadge`
  and `DirectionBadge` are its callers), **`ui/DataList.vue` + `ui/DataRow.vue`**
  (label/value pairs on record screens). `DataTable` takes an optional
  `rowTone` for a coloured left edge — reserved for "needs attention"; accent
  everything and it signals nothing.

## What a screen is allowed to show

A detail view answers a question; it is not a rendering of the table schema.
These rules are enforced by `frontend/tests/simplicity.spec.ts`, so breaking one
fails the suite rather than quietly lengthening a page.

- **`DataList`/`DataRow` drop blank values.** Pass `items` and a section with
  nothing in it collapses to one line plus an action, instead of eleven rows of
  em-dashes. `show-empty` restores the dashes and belongs only on a form, where
  the blank row *is* the affordance. `isBlank()` (in `lib/format.ts`) also
  treats `"—"` and `"— / —"` as empty, because the formatters emit those.
- **`lib/views.ts` is the single statement of what each list shows.** Columns
  live there, not inline in the page, and `columnsFor()` drops a column when a
  filter has pinned it (pick a status → the Status column goes) or when no row
  on screen can fill it (`showWhen`). A column that reads the same in every row
  is decoration — the test enforces this against the fixtures.
- **One filter bar per list** (`ui/ListToolbar.vue`): search and a secondary
  lens share a line, and there is exactly one pill row. Never two controls
  labelled "All".
- **One identifier per row.** Lead with the number a person quotes on the
  phone; the internal `CONT-…` name lives on the detail page.
- **One status, one place, one action.** The status badge in `DetailHeader` *is*
  the control (`#statusAction`); there is no second button and no "current
  status" card repeating it.
- **A panel with nothing in it does not render.** The shipment P&L card appears
  only once an invoice or purchase exists, and only for own-goods — on customer
  cargo it is their freight bill, not our margin. Own goods likewise render no
  consignee fields: there is nobody to consign to.
- **The portal never shows cost, margin, supplier or purchase.** Enforced twice:
  `simplicity.spec.ts` loads every portal route **as a real customer** (a staff
  session is redirected to the dashboard and would pass vacuously) with fixtures
  that deliberately include those keys, and
  `bwm_logistics/tests/test_portal_isolation.py` asserts the endpoints never
  return them and refuse another customer's record.
- **Two mobile-layout traps, both fixed globally — don't reintroduce them:**
  a responsive grid written as `grid sm:grid-cols-2` has *no* base column, so
  its implicit `auto` track takes a min-content floor and overflows a phone —
  always write `grid grid-cols-1 sm:grid-cols-2`. And a flex child that
  `truncate`s needs `min-w-0`, or its nowrap text becomes that floor. `style.css`
  also zeroes `min-width` on `input`/`select`/`textarea` for the same reason.
- **No decorative icons beside figures.** A stat tile is a number and its label;
  icons are for controls that need them (menu, close, buttons). This is a
  deliberate correction — the dashboard used to carry a coloured glyph per tile.
- **`ui/DataTable.vue` renders twice**: a table from `md` up, one stacked card
  per row below it, sharing the same `#cell-<key>` slots. Columns declare
  `primary` (card headline), `trailing` (pinned top-right), `mobileHidden`,
  `nowrap` and `hideWhenEmpty`. Never add a `min-w-[…]` table that a phone has
  to scroll. `hideWhenEmpty` drops a line from a *card* when the row has nothing
  to say for it — a table column must hold its slot in the grid, a card must
  not, so "Destination —" is pure noise. Pass a predicate when blank means
  something other than `isBlank`: an uninvoiced entry's amount is `0`, not
  empty.
- Shell: `AppShell.vue` is a single h-14 coal-900 top bar — **menu button left**
  (opens the one nav drawer, at every breakpoint), everyday tabs centre on
  desktop, **logo hard right**. No avatar menu, no Apps launcher, no "Switch to
  Desk"; Log out lives at the foot of the drawer. Mobile gets four plain bottom
  tabs — no raised action and no "More". Pages are lazy-loaded and route names
  double as access keys.

## The domain model (read this before touching Shipment or Container)

- **Container = the box, and its manifest.** `Container.contents` says what is
  inside and **whose it is**: an untagged line is the company's own goods, a
  tagged one names the customer whose cargo is riding in a consolidated box.
  This is what lets a milestone notification say "your 200 cartons" instead of
  a container number the customer cannot identify.
- **Shipment = the commercial booking.** Supplier, charges, invoice, and the
  `containers` table of every box it rides in. A purchase split across two
  40-footers is one booking. `Shipment.container` (single link) survives as
  "the primary box" because tracking events, the portal and older queries read
  it; `Shipment.sync_containers()` keeps it equal to the first row.
- **`Shipment.packages` is dead but not deleted.** The field and its rows remain
  so the `move_packages_to_containers` migration is reversible. Nothing reads
  it — don't add a caller. Note `get_shipment()` overwrites the `packages` key
  that `as_dict()` returns, because the print-label page builds one sticker per
  package from it.
- **`shipment.py` owns the one manifest resolver — always go through it.**
  `manifest_lines(containers, customer)` is "what does this party have in these
  boxes": `customer=None` means the untagged lines, i.e. ours. On top of it sit
  `Shipment.manifest()` (in-memory, so it is right during `validate`),
  `shipment_manifest(name)`, and `manifests_for([names])` — the batched form,
  for pages like Stock that ask about every booking at once.
  Totals, stock balances, the distribution guard, the printed label and the
  portal all resolve through these; each one used to read `Shipment.packages`
  for itself, which is how they came to disagree. **Per-customer billing out of
  a consolidated box is `manifest_lines()` with a different argument** — that is
  the extension point, not a new query.
- **A manifest line's `unit` and `description` default from the Item but are not
  dictated by it** (`fetch_if_empty`). The same goods ship in cartons on one
  booking and bags on the next; the line is the truth.
- **The distribution ledger keys on the Item, not on a name.**
  `Distribution Entry.item` is the join and `distribution_entry.line_key()` is
  the one place that says so — item where there is one, lowercased name for
  rows written before the catalogue existed. This is why renaming a manifest
  line is free: the name follows the link. Matching by string silently zeroed
  every entry recorded against a line the moment somebody corrected its
  spelling.
- **Editing a container reaches the bookings inside it.** The manifest lives on
  the box but the totals are cached on the shipment, so `Container.on_update`
  calls `refresh_stored_totals()` for every shipment riding in it — otherwise
  correcting a quantity leaves the booking, and the customer's portal, quoting
  the old number. `Container.check_distributed_contents()` blocks removing a
  line or cutting it below what has already gone out, and — like the shipment
  guard — objects only to what *this* save takes away, so a box whose numbers
  already disagreed stays correctable.
- **A distribution is never dropped from a balance.** `_balances()` gives an
  entry with no matching manifest line its own row with nothing received, so it
  reads as negative and is flagged `off_manifest`. Goods that left the yard do
  not disappear because somebody edited the packing list.
- **Contents point at ERPNext `Item`** (group `Logistics Goods`), classified by
  the `bwm_trade_direction` custom field so an export box is never offered
  import-only goods. Managed at `/items`; the picker can create one inline.
- **Statuses are Milestone Templates**, editable in Settings → Statuses. There
  is no separate Status doctype and there should not be — containers already
  link a template, and each milestone row carries its own `notify_customer`.
- **Tracking Event is append-only for Operations, correctable by a manager.**
  System Manager and Logistics Manager hold `write` + `delete`; Operations and
  Accounts hold read only. Note the Desk hides Delete when *no* role has the
  permission — that is why an admin could not remove one even though
  `has_permission()` says Administrator may. Deleting an event calls
  `resync_from_events()`, which re-derives `current_milestone`/`status` on the
  container and on every shipment in it from the events that remain — a
  shipment reads its container's events too, so rewinding one must look at
  both, and a record must never be left showing a milestone with an empty
  timeline behind it. `Cancelled` is a decision, not a milestone, so a rewind
  leaves it alone.
- **Consignee applies to customer cargo only.** On own goods the receiver is the
  company, so the fields don't render.

## Watch out for

- **`ex_beauty` may be copied from; `cargo_management` (AgileShift) must NOT be** — it's
  AGPLv3 and this app is MIT. Patterns only.
- **Frappe date filters are NULL-permissive.** `("<=", some_date)` compiles to
  `IFNULL(col, '') <= '<date>'`, and `''` sorts before every date — so rows
  where the column is *unset* match. `alerts.at_risk_containers()` needs its
  explicit `["demurrage_start_date", "is", "set"]` guard for exactly this
  reason; without it the demurrage banner flagged the entire active fleet.
  Assume any date `<=`/`<` filter needs the same guard.
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
