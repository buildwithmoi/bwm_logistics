# Logistics Software Market Research

**Purpose:** inform the [BWM Logistics PRD](PRD.md) — a Frappe/ERPNext SaaS covering
import/export container tracking with per-customer consolidation, courier/last-mile
delivery, a customer portal, notifications, and online payments.

**Date:** 2026-07-10

> **Methodology note.** Findings were gathered by a fan-out of web searches across five
> tracks, with claims extracted from fetched sources (mostly primary: vendor pages and
> GitHub repos, quoted directly). The planned adversarial verification pass could not run
> (session quota), so claims below are **sourced but single-source**; third-party pricing
> figures in particular should be re-confirmed before being used in sales or pricing
> decisions. Each claim links its source.

---

## Track 1 — Courier & last-mile delivery platforms

| Product | Positioning | Pricing (public) | What makes it stand out |
|---|---|---|---|
| **Onfleet** | Premium mid-market dispatch | ~$619 Launch / $1,349 Scale / $3,099 Enterprise per month | Polished dispatch UX + driver app; auto-dispatch; strong analytics; barcode-scan POD gated to higher tiers |
| **Bringg** | Enterprise delivery orchestration | Custom (enterprise) | Orchestrates across owned fleets + 3rd-party couriers + gig drivers; multi-fleet coordination |
| **FarEye** | Enterprise last-mile | Custom, volume/module-based (six-figure annual deals) | Predictive analytics, enterprise retail focus |
| **Locus** | Enterprise route optimization | Custom (six-figure) | Deep route optimization + dispatch automation |
| **Tookan** (Jungleworks) | Budget white-label | ~5× cheaper entry than Onfleet | Cheap white-label dispatch + driver apps; broad but shallower feature set |
| **Shipday** | SMB / restaurants & local e-commerce | **Free-forever entry plan**, paid tiers above | Free entry + driver network integrations; fastest way for a tiny courier to start |
| **Detrack** | Per-vehicle SMB pricing | ~$29/vehicle/month | ePOD depth (photo/signature/timestamp) + automated customer tracking links at commodity price |
| **Circuit** | Route planning first | Per-driver subscription | Planning-speed-focused daily routing for small fleets |
| **Onro** | White-label courier SaaS | Business $239/mo; Enterprise custom | **Closest architectural analog to this project**: bundles white-label customer app + driver app + self-service customer portal + dispatcher panel + COD + API/webhooks in one SaaS |

Sources: [Routific: Onfleet vs Bringg](https://www.routific.com/blog/onfleet-vs-bringg) ·
[Onfleet: Tookan vs Onfleet](https://onfleet.com/tookan-vs-onfleet) ·
[Locus: Locus vs FarEye vs Onfleet vs OptimoRoute](https://locus.sh/blogs/locus-vs-fareye-vs-onfleet-vs-optimoroute-2026/) ·
[Shipday 2026 ranking](https://www.shipday.com/post/best-last-mile-delivery-software-2026-ranking) ·
[Onro pricing](https://onro.io/pricing/) ·
[G2 last-mile category](https://www.g2.com/categories/last-mile-delivery)

**Table-stakes** (every serious player): dispatch board, driver mobile app, route
planning, ePOD (photo/signature), live tracking link for the customer, automated
email/SMS status notifications, COD recording.
**Differentiators:** auto-dispatch rules, route *optimization* (vs planning), multi-fleet
orchestration, white-labeling, predictive ETAs, analytics.

**Market shape:** pricing is sharply tiered — free/$29-level SMB tools (Shipday,
Detrack), mid-market ~$250–$1,500/mo (Onro, Onfleet), and six-figure enterprise
(Bringg, FarEye, Locus). The 2026 framing shift is from "routing tool" to **delivery
orchestration platform** ([overview](https://www.viewpointanalysis.com/post/last-mile-delivery-software-options-2026)).

---

## Track 2 — Container tracking / shipment visibility platforms

| Product | Model | Pricing (public) | What makes it stand out |
|---|---|---|---|
| **Terminal49** | API + dashboard | Publishes pricing; **free Developer Key tracks up to 100 containers**; 99.5% uptime claim | Push-based **webhook** API; 33+ carriers, 1,300+ US/CA terminals, rail; **terminal-level data: holds, fees, Last Free Day** → demurrage/detention avoidance |
| **Vizion** | Pure API ("the product is the API") | Transparent API pricing, ~few $/container; no free tier | Developer-first normalized container events across carriers/terminals for teams **building their own portals** |
| **ShipsGo** | Freemium tracker + API | **Credit-based: 1 credit = 1 tracked shipment (from ~$20 for 10)**; 100 req/min limit; ≥2 data refreshes/day | Cheapest entry; 160+ carriers; track by container / MBL / booking; webhooks + predictive ETA |
| **GoComet** | Visibility suite + procurement | Contact-sales, tiered | Bundles tracking with freight procurement/rate management; configurable event-based alerts; predictive ETA |
| **project44** | Enterprise multimodal visibility | Undisclosed; six-figure annual; implementations take quarters | 1,000+ carrier connections; AI predictive ETAs across ocean/air/truck/rail — priced out of SMB reach |
| **SeaRates** | White-label-friendly API | Subscription page (not per-container public) | Custom webhooks, rolled-cargo & delay notifications, embeddable demurrage/storage calculator |

Sources: [Terminal49 API page](https://terminal49.com/container-tracking-api) ·
[ShipsGo API page](https://shipsgo.com/ocean/container-tracking-api) ·
[GoComet API page](https://www.gocomet.com/container-tracking-api) ·
[SeaVantage: 8 platforms compared (2026)](https://www.seavantage.com/blog/best-container-tracking-software-in-2026-8-platforms-compared) ·
[Terminal49 comparison blog (Apr 2026)](https://terminal49.com/blog/best-container-tracking-software-in-2026-an-honest-comparison) ·
[SeaRates tracking API](https://www.searates.com/integrations/api-container-tracking/)

**Table-stakes:** track by container / BL / booking number; milestone events + ETA;
email alerts. **Differentiators:** webhook push (vs polling), terminal-level Last Free
Day / demurrage data, predictive ETA, exception dashboards, rail/intermodal.

**Key takeaway for this project:** visibility data is **buyable, not buildable** — for
V2 auto-tracking, ShipsGo (credit-based, ~$2/shipment) or Terminal49 (free ≤100
containers, then per-container) are realistic embedded suppliers for an SMB-priced SaaS;
their webhook models map cleanly onto our Tracking Event pipeline.

---

## Track 3 — Freight forwarding suites

| Product | Pricing (reported) | What makes it stand out |
|---|---|---|
| **CargoWise** (WiseTech) | ~$10k/mo entry, per-transaction; 2025 "Value Packs" reportedly raised costs 20–50%; 6–12 month implementations | The enterprise standard: global customs, multi-country compliance, deep EDI |
| **Magaya** | From ~$200/user/mo; 8–12 week implementation | Forwarding + **warehouse management** in one platform + Digital Freight Portal customer layer |
| **GoFreight** | Per-user subscription; live in 4–8 weeks | Modern cloud UX; **LCL consolidation with multi-shipper container management — CBM/weight calc, individual House BL per shipper, cost allocation**; US customs (AES/ISF/AMS); QuickBooks/Xero/Sage sync; branded customer portal |
| **Logitude** | From $75/user/mo, no implementation fees | Cheapest credible cloud forwarding suite |
| **Shipthis** | Custom | White-labeled end-to-end forwarding platform (quotation → docs → accounting → compliance) |

Sources: [GoFreight platform overview](https://gofreight.com/blog/gofreight-platform-overview) ·
[Ubico: 7 best CargoWise alternatives](https://www.ubico.io/post/the-7-best-cargowise-alternatives-for-freight-forwarders) ·
[CargoWise vs GoFreight](https://gofreight.com/blog/cargowise-vs-gofreight) ·
[SoftwareConnect roundup](https://softwareconnect.com/roundups/best-freight-forwarding-software/) ·
[Shipthis blog](https://www.shipthis.co/blog/freight-forwarding-software) · [Magaya](https://www.magaya.com/)

**The workflow that matters to us** (GoFreight's LCL consolidation model, which our
Container → Shipments design mirrors): one master container/BL carries multiple
shippers' cargo; the system computes each shipper's CBM/weight share, issues each an
individual **House BL**, allocates costs, and invoices per shipper. That is exactly the
"many customers tagged to one container" model — proof the PRD's core data model matches
industry practice.

---

## Track 4 — Customer portal & logistics payments UX

What a modern branded logistics portal offers (benchmark set):

- **Magaya Digital Freight Portal** — white-label 24/7 self-service: schedules, quotes,
  bookings, tracking, warehouse receipts, cargo releases, documents, invoices, **online
  invoicing & payment collection inside the portal**.
  [Source](https://www.magaya.com/digital-freight-portal/)
- **GoFreight Customer Portal** — real-time tracking, document downloads (BOL,
  commercial invoice, arrival notice, POD), invoice status, **pay directly from the
  portal** — all under the forwarder's own logo, colors, and domain.
  [Source](https://gofreight.com/product/customer-portal/)
- **PayCargo** — the freight-payment rail benchmark: vendors post invoices
  electronically, payers approve online, funds settle next morning; credit lines
  $50k–$5M; reported flat ~$7.50/transaction vs $25–40 cost of paper checks. Has a
  dedicated **Container Payment Portal** for paying demurrage/release fees online to
  expedite cargo release. [Payments](https://paycargo.com/payments/) ·
  [Container portal](https://paycargo.com/container-payment-portal/)
- **AfterShip branded tracking pages** — custom domain + brand assets, auto-translated
  status updates, and **customer self-subscription to email/SMS notifications** on a
  public tracking page. [Source](https://support.aftership.com/en/tracking/article/set-up-and-customize-the-branded-tracking-page-1f0j4o6)

**Portal feature checklist distilled** (adopted into PRD §4.6): shipment list +
timeline, track-by-number (public + logged-in), document access with visibility
control, invoice list + status + **pay now**, notification channel preferences,
operator branding everywhere.

---

## Track 5 — Frappe/ERPNext ecosystem prior art

| Prior art | What it is | Depth / adoption | Gaps vs this project |
|---|---|---|---|
| [**AgileShift/cargo_management**](https://github.com/AgileShift/cargo_management) | Freight-forwarding app on **Frappe v16 + ERPNext**. Workflow: parcel receipt via **Warehouse Receipt** (content, dims, weight) → **Cargo Shipment** consolidates receipts → **Cargo Shipment Receipt** sorts by customer → **per-customer Sales Invoices**. Carrier tracking via **EasyPost + 17Track webhooks** (USPS, UPS, DHL, FedEx, SF Express, Yanwen…) | Active: v16.2.0 (May 2026), 664 commits, 118★ / 86 forks. **AGPLv3** | **No customer portal, no online payments, no last-mile dispatch, Desk-only UX.** License forbids code reuse in an MIT app — patterns only |
| [**Freight Management** (Solufy, Frappe Cloud)](https://cloud.frappe.io/marketplace/apps/freight_management) | Air/ocean/land freight incl. FCL/LCL, FTL/LTL | 254 installs, 2 reviews, paid; only 3 advertised features (Direct Shipping, Customs Clearance, Track Order); supports v13–15 | Shallow public feature depth; no portal/notifications/payments visible |
| [**eShipz** (Frappe Cloud)](https://cloud.frappe.io/marketplace/apps/eshipz) | Multi-carrier parcel aggregator (200+ couriers, India-centric) extending the built-in **Shipment** DocType | Free; **41 installs**; polarized 3.0/5 rating | Parcel-only; no ocean/container, no dispatch/POD/portal |
| [**frappe/erpnext-shipping**](https://github.com/frappe/erpnext-shipping) | Official shipping integration (LetMeShip, SendCloud): rate comparison, labels, parcel tracking on the Shipment doctype | **MIT**, active (v16.0.0 Jul 2026), 140★ | Parcel-carrier only; establishes the extension pattern on `Shipment` |
| [**ERPNext built-ins**](https://frappe.io/erpnext/distribution/logistics-management-software) | `Shipment`, `Delivery Trip` (drivers, stops, ETA calc, route optimization), `Shipping Rule` (territory/distance/amount/weight rating), Packing Slip, Landed Cost Voucher | Core product | No container/BL tracking, no dispatch board, driver app, POD, tracking links, portal, or payment UX |
| [**frappe/payments**](https://github.com/frappe/payments) | Gateway-lifecycle framework: **Payment Gateway** (provider comms) + **Integration Request** (one attempt) + **reference doc** (defines "paid", usually Payment Request, via `on_payment_authorized`). Custom gateway = Settings DocType + `get_payment_url()` + `validate_transaction_currency()` | Official; Stripe/PayPal/Razorpay/Braintree/PayTM built-in; community Paystack/Flutterwave; a Paynow (Zimbabwe) gateway PR demonstrates African-provider extensibility | Framework only — portal payment UX is ours to build |

Additional deep-dive: [Building a real payment gateway for ERPNext with frappe/payments](https://donnclab.hashnode.dev/building-a-real-payment-gateway-for-erpnext-with-frappe-payments) (Jan 2026).

---

## Synthesis

### Table-stakes vs differentiators (across all tracks)

| Table-stakes (must have to be credible) | Differentiators (win deals) |
|---|---|
| Milestone tracking + timeline | Terminal-level demurrage / Last Free Day alerts |
| Customer email/SMS notifications | Webhook-fed **automatic** carrier tracking |
| Public tracking link/page | Predictive ETA |
| Driver ePOD (photo/signature) | Route optimization & auto-dispatch |
| Invoice generation | **In-portal online payment** |
| Role-based staff access | White-label branding per operator |
| REST API | Outbound webhooks for customers' systems |

### The gap this product fills

1. **No Frappe-ecosystem product combines container consolidation + customer portal +
   online payments + last-mile.** cargo_management proves the consolidation backend on
   Frappe but is Desk-only, AGPL, and has no portal/payments/dispatch. Marketplace apps
   are shallow or parcel-only. ERPNext core gives accounting/invoicing/rating primitives
   but zero customer-facing logistics UX.
2. **The incumbent tools that DO offer branded portals + payments (Magaya, GoFreight)
   start at ~$200/user/mo and 4–12 week implementations** — priced and scoped for
   established forwarders, not the SMB consolidators/couriers this SaaS targets.
3. **The industry-standard consolidation model (GoFreight's LCL flow) validates our data
   model**: master container → per-customer house shipments → cost allocation →
   per-customer invoicing.
4. **Visibility data is buyable**: ShipsGo/Terminal49-class APIs make V2 auto-tracking a
   per-container operating cost (~$2/container), not an R&D program.
5. **Onro's shape confirms the bundle** (courier + white-label portal + COD + API at
   $239/mo) — but it has no container/import-export dimension. Combining both sides in
   one product, on an ERP the operator owns, is the wedge.
