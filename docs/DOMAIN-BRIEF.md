# Domain brief — shipments, containers, items and status

Paste this into Claude Code in this repo, after `docs/SIMPLIFICATION-BRIEF.md`.
Read `CLAUDE.md` and `docs/PRD.md` first.

This changes the **data model**, so it comes before any more UI work — several
of the display problems in the simplification brief exist because the model
underneath them is wrong.

Three of the requests below are answered differently from how they were asked.
Those are marked **⚠ decided differently** with the reason. Read those first.

---

## 1. A shipment and a container are many-to-many

**Today:** `Shipment.container` is a single `Link`. One shipment, one container.

**Reality, and what the business actually does:**

- **One container, many shipments.** This is consolidation — the entire premise
  of the product per `docs/PRD.md`. Several customers' goods share one box.
- **One shipment, many containers.** A large customer's consignment fills two or
  three boxes.

Both happen, so the relationship is **many-to-many** and needs a join table.

### Build

A child table **`Shipment Container`** on Shipment:

| field | type | why |
|---|---|---|
| `container` | Link → Container | which box |
| `packages` | Int | how much of this shipment is in *that* box |
| `weight_kg`, `volume_cbm` | Float | per-container split, for cost allocation |

Keep `Shipment.container` for one release as a read-only mirror of the first
row so nothing breaks mid-migration, then delete it. Write a patch that copies
every existing `Shipment.container` into a row of the new table — do not leave
existing data behind.

**Container detail** then lists the shipments inside it (that is the manifest,
and the answer to "whose goods are in this box"). **Shipment detail** lists the
containers carrying it.

---

## 2. ⚠ Decided differently: customer tags belong on the shipment, not the container

**You asked for:** customer tags moved onto Container, because *"when making a
notification we can't send the actual container name to the customer because we
don't know which one exactly belongs to the customer."*

**The problem is real. The fix is different, and simpler.**

Once §1 exists, the join table already tells you exactly which containers carry
a given customer's shipment — that is what it is for. Tagging customers onto the
container as well would store the same fact twice, and the two copies would
disagree the first time a shipment moved boxes.

**The actual fix is to stop naming containers to customers at all.**

A customer knows their shipment reference (`BWM-000010`). They have never seen
`MNBU0367216` and it means nothing to them — it is your internal logistics fact,
and on a consolidated container it also leaks that other people's goods share
the box.

### Build

- **Notifications reference the shipment, never the container.** "Your shipment
  BWM-000010 has arrived at Tema" — not the container number.
- Where a container milestone should notify, resolve through the join table to
  every shipment inside it, and send one message **per shipment, to that
  shipment's customer**.
- Add a test: assert no notification template can render a container number.
  `Notification Log Entry` already exists — assert on its rendered body.

"Tagging a customer to a container" is then simply adding that customer's
shipment line to the container, which is the same action with a truthful name.

---

## 3. ⚠ Decided differently: packages are Items only for Own Goods

**You asked for:** packages moved off the Shipment form onto the Container, and
made `Item` records.

**Half of that is right.**

Splitting by shipment type:

- **Own Goods (Trading)** — you buy these, own them, and sell them. They are
  genuinely stock. `Item` is exactly right, `/stock` already exists, and
  `api/purchasing.py` already touches Item. Use `Item`.
- **Customer Cargo** — you never own these. They are somebody else's television
  in your box. Making them `Item` records would put another company's goods into
  your inventory valuation and your P&L. **Keep these as description lines.**

So `Shipment Package` stays, but gains an optional `item` Link used only when
`shipment_type = "Own Goods (Trading)"`.

**On moving packages to the Container:** do not. A container is a steel box; it
has a capacity, not a manifest of its own. What is in it is the sum of the
shipments inside it. Put the package lines on the **`Shipment Container` join
row** — "these 12 cartons of this shipment are in that box" — which is the fact
you actually need for a manifest, a customs entry, and cost allocation.

The container's contents view is then computed, never entered twice.

### On filtering items by import/export

You asked for the item field to show import items or export items depending on
the container's direction.

An item is not inherently an import or an export — a phone you import this month
you might export next month. Direction belongs to the shipment, not the thing.

Build it as a **convenience filter, not a constraint**: use `Item Group`
("Imports", "Exports"), default the picker to the matching group, and let the
user clear the filter. Never reject an item because of its group.

---

## 4. Consignee: your confusion is the design telling you something

**You asked:** *"why do we have the consignee, the receiver? Is that not supposed
to be the company that's making the imports and exports, and if yes why don't we
autofill with the company name?"*

Both answers are correct, for different shipment types — which is why the single
field is confusing.

The consignee is the party named on the Bill of Lading who takes delivery and
clears customs. So:

- **Own Goods** — you are importing your own stock. The consignee **is your
  company**. Autofill it, make it read-only, and label the section "Customs".
- **Customer Cargo** — the goods belong to the customer. The consignee is **the
  customer**, or somebody they nominate to collect. Default it from the selected
  customer, and leave it editable, because a nominee is common and legitimate.

### Build

- Default `consignee_name` / `consignee_phone` from shipment type as above.
- When it equals the default, **do not render it as a field at all** — show one
  line: "Consigned to you" or "Consigned to {customer}". Only show the inputs
  when someone chooses to override.
- That removes two of the four consecutive em-dashes currently at the top of
  Shipment detail.

---

## 5. Supplier on the shipment

Straightforward, and Frappe's `Supplier` already exists — `api/purchasing.py`
touches it.

- Add `supplier` (Link → Supplier) to Shipment.
- **Only meaningful for Own Goods** — a customer's cargo has no supplier of
  yours. Hide the field entirely for Customer Cargo.
- Expose Supplier in the frontend the same way Customers already are: a list, a
  create dialog, and a `SearchCombo` on the shipment form. `Customers.vue` and
  `dialogs/customer.png` are the pattern to copy — do not invent a second one.

---

## 6. Own Goods first

`shipment_type` currently lists **Customer Cargo** then **Own Goods (Trading)**,
and `ShipmentNew.vue` renders them in that order with Customer Cargo
preselected.

Swap them. Own Goods is the common case, so it goes first and is the default.
Change the `Select` option order on the DocType **and** the card order in
`ShipmentNew.vue` — they must not disagree.

---

## 7. ⚠ Decided differently: you already have a status doctype

**You asked for:** a Status DocType so the company can define its own statuses.

**`Milestone Template` and `Milestone Template Item` already exist**, with a
`direction` field and an ordered child table. That is the configurable-stages
mechanism. Building a second one would leave two places defining what a
container can be, and a container that is `In Transit` by one and `Arrived` by
the other.

What is actually wrong is that **`Container.status` and `Shipment.status` are
hardcoded `Select` fields** alongside it — `Active/Completed/Cancelled` and
`Open/In Transit/Arrived/…`. So the app has a configurable milestone system *and*
two fixed status lists, which is why the detail screens show status twice.

### Build

Extend what exists rather than adding to it:

- Give `Milestone Template Item` the fields a status needs: `is_terminal`
  (Completed/Cancelled), `colour`, and `notify_customer`.
- Add `applies_to` (Container / Shipment) to `Milestone Template` so the two
  entities can have different stage sets from one mechanism.
- Replace the hardcoded `Select` on both DocTypes with a `Link` to the milestone
  item, keeping the old value in a deprecated field until a patch has migrated
  every row.
- The **lifecycle** state (Active / Completed / Cancelled) is a different thing
  from the **stage** (In Transit / Arrived) and should stay a small fixed
  Select. Do not let a company invent a fourth lifecycle state — code branches
  on it.

Write the patch. Do not leave existing containers with an empty status.

---

## 8. Shipment detail: sections without a longer page

`ShipmentDetail.vue` is **780 lines**, the largest file in the app, and after §1
it gains a containers list too.

- **Desktop** — a left rail inside the page listing sections (Overview,
  Containers, Packages, Charges, Documents, Timeline), content on the right.
  This is the console pattern; it does not scroll.
- **Mobile** — **not** a side menu, and not another tab row: there is already a
  bottom tab bar and a second one would compete with it. Use collapsible
  sections, **open only when they have content**, closed when empty. That
  composes with the `hideEmpty` change in the simplification brief rather than
  fighting it.
- Split the file per section while you are in there. One component per section,
  each deciding its own emptiness.

---

## 9. The status sheet does not show the current status

When you open the status sheet on a shipment that already has a status, nothing
is marked as selected — so the sheet reads as "pick a status" rather than "this
is where it is, move it".

Fix: pass the current value in, mark it selected, and disable it as a choice —
re-selecting the status it already has should not create a `Tracking Event`
saying it changed. Check `Tracking Event` is not written when the value is
unchanged.

---

## Order of work

1. §7 status — everything else displays it.
2. §1 join table + patch — the structural change.
3. §4 consignee and §5 supplier — small, and they remove empty rows.
4. §3 packages onto the join row, Items for Own Goods only.
5. §2 notifications through the join.
6. §6 swap, §9 status sheet — minutes each.
7. §8 sections — last, once the content is settled.

## Tests

- A shipment with **two containers** and a container with **three shipments**
  both render, on phone and desktop.
- The migration patch: every existing `Shipment.container` became a join row,
  and no shipment lost its container.
- **Customer Cargo never creates an `Item`** and never appears in stock
  valuation.
- No notification body contains a container number — assert on the rendered
  `Notification Log Entry`.
- Consignee defaults: Own Goods gives the company, Customer Cargo gives the
  customer, and an override survives a save.
- Supplier does not render for Customer Cargo.
- Re-selecting the current status writes **no** `Tracking Event`.
