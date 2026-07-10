# BWM Logistics — Project Requirements Document (PRD)

| | |
|---|---|
| **Product** | BWM Logistics — SaaS logistics platform |
| **Stack** | Frappe v16 + ERPNext v16 backend · Vue 3 (TypeScript) frontend |
| **Status** | Draft v1.0 |
| **Date** | 2026-07-10 |
| **Companion doc** | [market-research.md](market-research.md) — full market research with sources |

---

## 1. Executive summary & product vision

**BWM Logistics** is a multi-tenant SaaS platform for logistics operators who run two
intertwined businesses:

1. **International container logistics (import & export)** — the operator books/receives
   sea (and air) containers. Many customers' goods travel **consolidated inside one
   container**. The operator must track each container's journey milestone-by-milestone
   and keep every tagged customer informed automatically.
2. **Local courier & last-mile delivery** — once goods clear, the operator picks up,
   dispatches, and delivers packages to customers' doors (or customers arrange pickup),
   with proof of delivery.

Around these operations sits a **customer experience layer** that most small/mid-size
operators in this market lack — and that the incumbent enterprise tools (CargoWise,
Magaya) only offer at enterprise prices:

- a **branded public website** with company information and a customer login,
- a **self-service customer portal** — track shipments, see milestone timelines, view
  invoices, **pay online**,
- **automatic notifications** (email + SMS at MVP) at every milestone, driven by which
  customers are tagged to a container/shipment,
- a **REST API** for integrations.

**Vision statement:** *give small and mid-size logistics operators the customer
experience of a global forwarder — container visibility, proactive notifications, and
online payments — at SaaS pricing, on an open ERP core (ERPNext) they fully own.*

### Why Frappe/ERPNext

- Accounting, invoicing, payment tracking, customers, taxes, and multi-currency come free
  from ERPNext instead of being rebuilt.
- Frappe gives role-based permissions, REST API, email/SMS delivery, document versioning,
  and per-tenant deployment (site-per-tenant) out of the box.
- Prior art proves the model works ([cargo_management](https://github.com/AgileShift/cargo_management)
  runs freight forwarding on Frappe v16 + ERPNext) — but it is Desk-based and has **no
  customer portal, no online payments, and no polished operator UX**. That gap is this
  product.

---

## 2. Market research summary

> Full research with per-claim sources: [market-research.md](market-research.md).

### The landscape in one view

| Category | Leaders | Pricing shape | What they prove |
|---|---|---|---|
| Courier / last-mile | Onfleet (~$619–$3,099/mo), Bringg, FarEye, Locus (enterprise custom), Tookan, Shipday (free entry), Detrack (~$29/vehicle/mo), **Onro** ($239/mo, white-label + portal + COD + API) | Free → $29 → $250–1,500/mo → six-figure | Dispatch board, driver app, ePOD, tracking links, and notifications are **table-stakes**; white-label + portal bundling at SMB price (Onro) is the proven shape |
| Container visibility | **Terminal49** (free ≤100 containers, webhook push, Last Free Day data), **ShipsGo** (1 credit = 1 shipment, ~$2), Vizion (pure API), GoComet, project44 (six-figure enterprise) | Few $/container (API) → six-figure (enterprise) | Visibility data is **buyable via webhook APIs** — auto-tracking is an operating cost, not an R&D program |
| Freight forwarding suites | CargoWise (~$10k/mo entry, 6–12 mo rollout), **Magaya** (~$200/user/mo), **GoFreight** (4–8 wk rollout), Logitude ($75/user/mo), Shipthis | Per-user/mo or per-transaction | GoFreight's **LCL consolidation flow** (master container → per-shipper House BL → cost allocation → per-shipper invoice) validates our exact data model |
| Portal & payments UX | Magaya Digital Freight Portal, GoFreight portal, PayCargo (~$7.50/txn, container payment portal), AfterShip branded tracking | Bundled or per-transaction | The modern portal checklist: tracking, docs, invoices, **pay-in-portal**, notification prefs, operator branding |
| Frappe ecosystem | cargo_management (AGPL, Desk-only), Solufy Freight Management (254 installs), eShipz (41 installs), frappe/erpnext-shipping (MIT, parcels), ERPNext built-ins, frappe/payments | Free/OSS or small paid | Consolidation works on Frappe (cargo_management) — but **nobody ships portal + payments + last-mile + container tracking together** |

### Gap / opportunity statement

1. **Ecosystem gap**: no Frappe/ERPNext product combines container consolidation +
   customer portal + online payments + last-mile dispatch. The closest (cargo_management)
   is Desk-only, AGPLv3, and explicitly lacks all three customer-facing pillars.
2. **Price/complexity gap**: the incumbent products that do offer branded portals with
   payments (Magaya, GoFreight) cost ~$200+/user/mo with multi-week implementations —
   out of reach of the SMB consolidators and couriers this SaaS targets.
3. **Model validation**: the industry-standard LCL consolidation workflow matches our
   Container → tagged Shipments → per-customer invoicing design one-to-one.
4. **Feasible differentiators** (from the research's table-stakes-vs-differentiator
   analysis): in-portal payment, notification tagging, white-label branding at MVP;
   webhook auto-tracking + demurrage alerts at V2 via ShipsGo/Terminal49-class APIs.

---

## 3. Users & personas

| Persona | Role in system | Primary surface | Goals |
|---|---|---|---|
| **Operator admin** (business owner) | `Logistics Manager` | Operator app (Vue) | See KPIs, configure rates/branding/gateways, manage staff access |
| **Operations officer** | `Logistics Operations` | Operator app | Create containers & shipments, tag customers, record milestones, trigger notifications, generate invoices |
| **Dispatch officer** | `Logistics Operations` | Operator app (Dispatch) | Schedule pickups/deliveries, assign drivers, monitor runs |
| **Driver / courier** | `Logistics Driver` | Operator app (mobile web, driver view) | See assigned stops, capture proof of delivery, collect COD |
| **Customer** (importer/exporter/consignee) | `Logistics Customer` (website user) | Customer portal (Vue) + public site | Track "where is my shipment", get notified, download docs, pay invoices online |
| **Finance officer** | `Logistics Accounts` | Operator app (Billing) + Desk | Invoices, payments, reconciliation (full accounting stays in ERPNext Desk) |
| **Platform admin** (BWM) | `System Manager` | Frappe Desk | Tenant provisioning, upgrades, support |

**Access model:** staff log in → **operator app**; customers log in → **customer
portal**; System Managers may also reach **Desk**. Users only see the pages/actions
their role allows (see §4.2).

---

## 4. Functional requirements

Requirement priorities: **[MVP]** must ship first release · **[V1]** fast-follow ·
**[V2]** later.

### 4.1 Public website

- **FR-WEB-1 [MVP]** A server-rendered, SEO-friendly public landing page at the site root
  presenting the company: hero, services (import/export container shipping, courier &
  delivery), how-it-works, contact/location, and a prominent **Login** button that leads
  to the SPA login. Branded gold/black/white.
- **FR-WEB-2 [MVP]** Standard/static page implemented as a Frappe web page/template under
  `www/` — one template, content edited in code for now.
- **FR-WEB-3 [MVP]** A **public track-by-number widget**: enter a tracking number →
  milestone timeline (guest-accessible, rate-limited, shows no personal data beyond the
  shipment's own status).
- **FR-WEB-4 [V2]** Make the site content dynamic (CMS-editable per tenant: logo, colors,
  copy, sections) so every tenant gets their own branded site.

### 4.2 Authentication, roles & access control

- **FR-AUTH-1 [MVP]** Single Frappe login (stock `/api/method/login`). After login, a
  `login_destinations` API decides where the user lands: staff → operator app; customer →
  customer portal; System Manager → chooser incl. Desk. *(Adopts the ex_beauty
  architecture.)*
- **FR-AUTH-2 [MVP]** Page/action-level access API (`my_permissions`) returns the pages a
  user can see and the actions they can perform; the SPA hides nav items/pages/buttons
  accordingly. **Server-side permissions remain the source of truth** — every whitelisted
  method re-checks roles.
- **FR-AUTH-3 [MVP]** Roles shipped by the app: `Logistics Manager`, `Logistics
  Operations`, `Logistics Driver`, `Logistics Accounts`, `Logistics Customer`.
- **FR-AUTH-4 [MVP]** **Customer onboarding is staff-driven**: creating a Customer with a
  portal login sends Frappe's standard welcome email with a **set-new-password link**. No
  self-signup at MVP.
- **FR-AUTH-5 [MVP]** Customers are **website users** (no Desk access); a customer's
  portal session can only query documents linked to their own Customer record
  (server-enforced via permission query conditions).
- **FR-AUTH-6 [V1]** Password reset, session management, optional 2FA (Frappe built-in).

### 4.3 Container & shipment tracking (import/export)

- **FR-CTR-1 [MVP]** **Container** records with: container number (ISO format validated),
  size/type (20GP/40GP/40HC/45HC/reefer…), direction (**Import**/**Export**), shipping
  line, vessel & voyage, Bill of Lading (master BL) number, booking number, seal number,
  port of loading, port of discharge, ETD/ATD, ETA/ATA, customs status, free days &
  demurrage start, current status.
- **FR-CTR-2 [MVP]** **Milestone tracking** per container from a configurable **Milestone
  Template** per direction — e.g. Import: `Booked → Loaded at Origin → Vessel Departed →
  In Transit → Arrived at Port → Customs Clearance → Released → At Warehouse → Ready for
  Delivery/Pickup → Delivered`. Export mirrors this. Operations record milestone events
  (timestamp, location, note); every event is an immutable **Tracking Event** log entry.
- **FR-CTR-3 [MVP]** Container list & board views with status filters, ETA sorting, and
  exception flags (overdue vs ETA, demurrage at risk based on free days).
- **FR-CTR-4 [MVP]** Documents on container/shipment: attach BL, packing list, customs
  entries; visibility flag controls what customers can see/download in the portal.
- **FR-CTR-5 [V2]** **Carrier-API auto-tracking**: integrate a container-visibility API
  (Terminal49 / ShipsGo / Vizion class) so vessel milestones stream in automatically
  instead of manual entry; manual entry stays as fallback.
- **FR-CTR-6 [V2]** Predictive ETA and demurrage/detention alerting on API data.

### 4.4 Consolidation & customer tagging (the core model)

- **FR-CON-1 [MVP]** **Shipment (house consignment)**: one customer's goods within (or
  outside) a container. Fields: customer, linked container (optional — a shipment can be
  loose cargo/air), own **tracking number** (auto-generated, customer-facing), shipper &
  consignee details, origin/destination, package lines (description, qty, weight, volume,
  declared value), charges, status.
- **FR-CON-2 [MVP]** **Many shipments → one container** (consolidation). Tagging a
  customer's shipment to a container is what subscribes that customer to the container's
  milestone notifications.
- **FR-CON-3 [MVP]** Container milestone events **cascade** to all tagged shipments: when
  "Vessel Departed" is recorded on the container, every linked shipment gets the event on
  its own timeline and each tagged customer is notified once.
- **FR-CON-4 [MVP]** Shipment-level events also exist independently (e.g. "Package
  received at origin warehouse", "Out for delivery") for the pre/post-container legs.
- **FR-CON-5 [V1]** Warehouse receipt flow at origin/destination: receive packages,
  weigh/measure, photo, label print with tracking number/barcode.
- **FR-CON-6 [V1]** Barcode/QR scanning to receive and load packages into containers.

### 4.5 Courier & last-mile delivery

- **FR-DEL-1 [V1]** **Pickup Request**: customers request pickup from the portal (address,
  packages, preferred window); operations approve & schedule.
- **FR-DEL-2 [V1]** **Dispatch board**: unassigned deliveries/pickups vs drivers; assign
  stops into a **Delivery Run** (reuse/extend ERPNext `Delivery Trip` + `Driver` +
  `Vehicle`); run statuses `Scheduled → In Transit → Completed`.
- **FR-DEL-3 [V1]** **Driver view** (mobile-responsive route in the operator SPA): my
  stops for today, navigate (map link), mark arrived/delivered/failed with reason.
- **FR-DEL-4 [V1]** **Proof of delivery**: receiver name, signature capture, photo,
  timestamp, geolocation; visible to the customer in the portal.
- **FR-DEL-5 [V1]** **COD**: record cash collected against the shipment's invoice;
  reconcile per driver per run.
- **FR-DEL-6 [V2]** Route optimization (stop sequencing) and live driver location on a map;
  customer "driver is nearby" notification.

### 4.6 Customer portal

- **FR-POR-1 [MVP]** Portal home: my active shipments at a glance with status chips +
  track-by-number box.
- **FR-POR-2 [MVP]** Shipment detail: **milestone timeline** (container + shipment events
  merged), package list, linked documents (where marked visible), invoice(s) and payment
  status.
- **FR-POR-3 [MVP]** **Invoices & payments**: list my invoices (from ERPNext Sales
  Invoice), view/download PDF, **Pay now** → online payment (§4.8).
- **FR-POR-4 [MVP]** Profile: contact info, delivery addresses, notification preferences
  (which channels).
- **FR-POR-5 [V1]** Create pickup requests; message/support thread per shipment.
- **FR-POR-6 [V2]** In-portal notification center (bell) + browser push.

### 4.7 Notifications

- **FR-NOT-1 [MVP]** **Email + SMS** on milestone events. Email via Frappe Email Account;
  SMS via Frappe **SMS Settings** (pluggable HTTP gateway — e.g. Hubtel, Twilio, Africa's
  Talking) so each tenant configures their provider.
- **FR-NOT-2 [MVP]** **Notification Templates** per (event type × channel) with variables
  (`{customer_name}`, `{tracking_no}`, `{milestone}`, `{eta}`, `{tracking_link}`);
  sensible defaults shipped, editable per tenant.
- **FR-NOT-3 [MVP]** Recipients resolved by tagging: container event → all customers with
  shipments tagged to it; shipment event → that customer. Per-customer channel opt-in/out.
- **FR-NOT-4 [MVP]** **Notification Log**: every send recorded (recipient, channel,
  event, status, error) — operators can see "who was told what, when"; failed sends
  retried/flagged.
- **FR-NOT-5 [V2]** WhatsApp channel (Meta WhatsApp Business API) and portal push.

### 4.8 Billing & payments

- **FR-PAY-1 [MVP]** **Rate Cards**: operator-defined pricing — per kg / per CBM / per
  package type / flat per route or zone, plus standard extra charges (customs, handling,
  delivery). Used to compute shipment charges.
- **FR-PAY-2 [MVP]** Generate **ERPNext Sales Invoice** from a shipment's charges (one
  click); multi-currency supported by ERPNext.
- **FR-PAY-3 [MVP]** **Online payment**: "Pay now" creates an ERPNext **Payment Request**
  routed through the **frappe/payments** gateway framework — Stripe/PayPal built-in;
  Paystack/Flutterwave (cards + **mobile money**) via community gateway apps. Successful
  payment auto-creates the Payment Entry and reconciles the invoice.
- **FR-PAY-4 [MVP]** Payment confirmation notification to customer + operator; shipment
  can be configured to require payment before "Release/Delivery" milestone.
- **FR-PAY-5 [V1]** COD collection & driver reconciliation (with §4.5).
- **FR-PAY-6 [V2]** Customer statements, partial payments, deposits/wallets.

### 4.9 REST API & webhooks

- **FR-API-1 [MVP]** All SPA traffic uses **whitelisted methods** under
  `bwm_logistics.api.*` (thin, role-checked, JSON) — this *is* the public REST surface,
  documented in the repo.
- **FR-API-2 [MVP]** Guest tracking endpoint: `GET track(tracking_no)` → sanitized
  milestone timeline (rate-limited).
- **FR-API-3 [V1]** Token-based access (Frappe API key/secret) for third parties:
  shipments CRUD, tracking events, invoice status.
- **FR-API-4 [V2]** **Outbound webhooks**: tenant-configurable URLs receiving milestone /
  payment events (HMAC-signed).

---

## 5. Non-functional requirements

- **NFR-1 Multi-tenancy**: one Frappe **site per tenant** (standard Frappe Cloud model).
  No cross-tenant data paths by construction. Tenant branding (logo, company info,
  gateways, SMS provider) configured per site in **Logistics Settings**.
- **NFR-2 Security**: server-side role enforcement on every endpoint; customers can only
  read their own documents (permission query conditions); CSRF on all SPA calls; files
  marked customer-visible are the only ones served to portal users; guest tracking
  endpoint returns no PII and is rate-limited.
- **NFR-3 Auditability**: Frappe document versioning on all operational DocTypes;
  Tracking Events and Notification Logs are append-only.
- **NFR-4 Performance**: operator list views paginate server-side (DataTable
  load-more pattern); dashboard KPI queries aggregated server-side; SPA lazy-loads
  routes. Target < 500 ms p95 for list/detail API calls on typical tenant data.
- **NFR-5 Mobile**: operator app responsive; **driver view designed mobile-first**;
  portal fully responsive.
- **NFR-6 i18n & locale**: strings translatable (Frappe `__()`/`_()`), per-site timezone,
  currency, and number formats from ERPNext settings.
- **NFR-7 Reliability**: notification sending is queued (background jobs), retried, and
  logged; payment webhooks idempotent.

---

## 6. Technical architecture

### 6.1 Apps & module layout

```
bench (fb-16-6)
├── frappe (v16)
├── erpnext (v16)            # accounting, customers, invoicing, payments plumbing
├── payments (frappe/payments) # payment gateway framework  ← ADD to bench
└── bwm_logistics            # this app
    ├── bwm_logistics/       # Python: doctypes, api/, notifications, portal logic
    │   ├── api/             # whitelisted methods: access.py, track.py, portal.py,
    │   │                    #   containers.py, shipments.py, dispatch.py, billing.py,
    │   │                    #   dashboard.py
    │   └── www/             # public landing page + SPA host page
    └── frontend/            # Vue 3 SPA (replaces current logistics/ scaffold)
```

### 6.2 ERPNext reuse map

| Need | Reuse from ERPNext/Frappe | New in bwm_logistics |
|---|---|---|
| Customers, addresses, contacts | `Customer`, `Address`, `Contact` | Portal-user link + tagging |
| Invoicing, taxes, currency | `Sales Invoice`, `Payment Entry`, `Mode of Payment` | Charge computation → invoice generation |
| Online payment | `Payment Request` + **frappe/payments** gateways (Stripe, PayPal; Paystack/Flutterwave community) | Portal "Pay now" flow, payment-gated milestones |
| Drivers & vehicles | `Driver`, `Vehicle`, evaluate `Delivery Trip`/`Delivery Stop` | Dispatch board UX, POD, COD |
| Email | Email Account, Email Queue | Milestone templates & recipient resolution |
| SMS | Frappe `SMS Settings` (pluggable gateway) | Per-event SMS templates + log |
| Roles/permissions | Frappe roles, permission query conditions | 5 logistics roles + access API |
| **Not reused** | ERPNext `Shipment` (single-carrier parcel booking — no container/consolidation model) | Custom `Container`/`Shipment` doctypes |

### 6.3 New DocTypes (draft)

**Masters/setup:** `Logistics Settings` (single) · `Shipping Line` · `Port` ·
`Container Type` · `Milestone Template` (+ child `Milestone Template Item`) ·
`Rate Card` (+ child `Rate Card Item`) · `Notification Template`

**Operational:** `Container` · `Shipment` (+ child `Shipment Package`) ·
`Tracking Event` (append-only log, links container/shipment) · `Pickup Request` ·
`Proof of Delivery` · `Notification Log`

**Dispatch (V1):** extend `Delivery Trip`/`Delivery Stop` via custom fields, or a slim
`Delivery Run` if Trip proves too rigid — decided during V1 design spike.

### 6.4 Frontend architecture (adopted from ex_beauty)

The existing `logistics/` scaffold (doppio libs, Options API, plain CSS) is **replaced**
by a `frontend/` app copying **ex_beauty's architecture**:

- **Stack**: Vue 3.5 + TypeScript (`<script setup>`), Vite, **Tailwind CSS** with
  shadcn-vue conventions (`cn()` = clsx + tailwind-merge, CVA variants), **reka-ui**
  headless primitives, **lucide-vue-next** icons, **Pinia**, socket.io for realtime.
  No frappe-ui/doppio — a thin `lib/frappe.ts` `call()` client with CSRF + error
  normalization (~20 lines, per ex_beauty).
- **Shell**: top-bar-only `AppShell` (h-14 **black** bar), logo tile + business name,
  pill nav tabs, right cluster (Apps drawer, notifications, avatar menu with
  Switch-to-Desk/Logout), mobile slide-in drawer.
- **Apps drawer**: grid of app tiles (Core: Dashboard, Containers, Shipments, Dispatch,
  Customers, Billing · Setup: Settings, Staff, Rate Cards) with tinted icon tiles.
- **Session & access**: Pinia `session` store reads server-injected boot;
  `api/access.py` exposes `my_permissions` (→ `canSee(key)` / `can(page, action)`) and
  `login_destinations` (staff → `/`, customer → `/portal`, SM → chooser incl. Desk);
  router guard redirects to first allowed page; `RoleGate` component for restricted UI.
- **One SPA, two route trees** (lazy-loaded):
  - **Operator**: `/` bento dashboard (KPIs: containers in transit, arriving this week,
    unpaid invoices, deliveries today) · `/containers` board+list, `/containers/:id`
    detail (milestones, tagged shipments, docs) · `/shipments`, `/shipments/:id` ·
    `/dispatch` (V1) · `/customers`, `/customers/:id` · `/billing` · `/notifications`
    (log) · `/settings` (SubNav rail: company, rates, milestones, templates, gateways,
    staff access)
  - **Customer portal**: `/portal` home + track box · `/portal/shipments`,
    `/portal/shipments/:id` timeline · `/portal/invoices` (+ pay) · `/portal/profile`
- **List-page pattern**: header (h1 + primary Button) → clickable stat/filter cards →
  DataTable (selection, sort, server-side load-more) with kebab row menus.
- **Public site**: server-rendered Jinja page(s) in `www/` sharing the same design
  tokens (compiled CSS), with the guest track widget calling `api/track`.

### 6.5 Design system — gold / black / white

Everything structural from ex_beauty is kept (radius ladder `lg→xl→2xl→3xl→full`,
shadow scale `xs/card/pop/modal`, system-ui font stack, `.label-caps`, bento dashboard,
`tabular-nums`); only brand tokens change:

| Token | ex_beauty (rose/navy) | BWM Logistics (gold/black/white) |
|---|---|---|
| `brand` scale 50–900 | rose ramp, primary `#cd2f6a` (600) | gold ramp, e.g. 50 `#fdfaee` · 100 `#faf2d4` · 200 `#f4e3a8` · 300 `#eccf72` · 400 `#e3b84a` · 500 `#d4a12b` · **600 `#b8860b`** (primary CTA) · 700 `#96690a` · 800 `#7a540e` · 900 `#654510` |
| Top bar / `navy` | `#1e2547` navy | **near-black `#0f0f10`** (bar), black scale for overlays |
| `--primary` / `--ring` | `338 62% 49%` | `~43 89% 38%` (gold-600) |
| Chart accents | pink `#fb4587` + orange/purple/cyan/emerald | gold `#d4a12b` primary series + slate/amber/emerald/cyan accents |
| Dark ribbon / CTA tiles | `bg-gray-900` | kept — black is now also the brand neutral |
| Login gradient blobs | pink pastels | soft golds (`#f7e8b8`, `#e3b84a`, `#d4a12b` glow) |

Swap points (from the ex_beauty audit): Tailwind `brand`+`navy` scales, CSS vars
`--primary`/`--ring`, hardcoded `bg-[#1e2547]` in AppShell, chart hexes in
Dashboard/StatTile/AppsDrawer tints, Login blobs. Contrast rule: **gold is never used
for body text on white** — it's for CTAs, active states, tints, and accents; text stays
near-black ink.

### 6.6 Notification pipeline

```
Milestone recorded (Container/Shipment)
  → Tracking Event (append-only)
  → enqueue notify job
     → resolve recipients (tagged customers ∩ channel opt-ins)
     → render Notification Template (event × channel)
     → send: Email Queue / SMS Settings gateway
     → write Notification Log (status, error, retry)
  → realtime push to operator SPA (socket.io)
```

---

## 7. Phased roadmap

| Phase | Scope | Exit criteria |
|---|---|---|
| **P0 — Foundation** | `frontend/` scaffold on ex_beauty stack + gold/black/white tokens; `ui/` + `bento/` component kit; auth (`login_destinations`), roles, access API; AppShell + Apps drawer; public landing page in `www/`; add **payments** app to bench | Staff and customer log in and land on the right (empty) surfaces; public page live |
| **P1 — MVP** | Containers + milestones (templates, events) · Shipments + packages + customer tagging + cascade · operator dashboard, container/shipment/customer pages · email+SMS notifications with templates & log · guest track widget · portal (home, shipments, timeline, invoices) · rate cards → Sales Invoice · **online payments** via Payment Request/gateways | An operator runs a real import container end-to-end: create → tag customers → record milestones → customers notified, track online, pay invoice online |
| **P2 — V1** | Pickup requests · dispatch board + delivery runs (Delivery Trip reuse decision) · driver mobile view · POD (signature/photo) · COD reconciliation · warehouse receipt + barcode labels · API tokens for third parties | A package is picked up, dispatched, delivered with POD; COD reconciled |
| **P3 — V2** | Carrier-API auto-tracking (Terminal49/ShipsGo class) · predictive ETA + demurrage alerts · WhatsApp + portal push · route optimization + live driver map · dynamic/CMS public site · outbound webhooks | Container milestones arrive without manual entry; tenant-branded dynamic site |

---

## 8. Open questions & risks

| # | Question / risk | Notes |
|---|---|---|
| 1 | **SaaS distribution** — Frappe Cloud marketplace vs self-hosted benches per tenant? | Affects pricing, update cadence, and how Logistics Settings onboarding is designed. |
| 2 | **cargo_management is AGPLv3** | Patterns may inform us; **code must not be copied** into this MIT app. |
| 3 | ERPNext `Delivery Trip` fitness for dispatch UX | Decide in P2 spike: custom fields on Trip vs slim custom `Delivery Run`. |
| 4 | SMS provider default | Frappe SMS Settings is provider-agnostic; ship configs/presets for common providers (Hubtel, Twilio, Africa's Talking). |
| 5 | Mobile money coverage | Paystack/Flutterwave community gateways vary in maintenance quality; validate against target markets before committing per-tenant. |
| 6 | Container-visibility API cost (V2) | Terminal49/Vizion/ShipsGo pricing is per-container/API-call; needs per-tenant pass-through pricing decision. |
| 7 | Driver app as PWA vs native later | Driver view ships as responsive web (P2); revisit native only if offline capture becomes a hard requirement. |
