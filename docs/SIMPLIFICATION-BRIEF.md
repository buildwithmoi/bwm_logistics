# Simplification brief — paste this into Claude Code in this repo

You are working on `bwm_logistics`. Read `CLAUDE.md` and `docs/PRD.md` first.

This is a **simplification** task, not a feature task. Nothing below asks for a
new capability. Every item removes something, hides something, or replaces
several things with one. If you find yourself adding a screen, you have
misread it.

Work through it in order. Verify each part before moving on — `yarn shots`
already exists and is the tool for this. Commit in small, legible steps.

---

## The one finding everything else follows from

`frontend/src/components/ui/DataRow.vue` renders an em-dash when a value is
empty, on purpose:

```
// Empty renders an em-dash rather than collapsing, so a half-filled
// record still reads as a form you can complete.
```

That reasoning is right for a **form** and wrong for a **detail view**, and the
app uses the same component for both. The result, in the current screenshots:

- **Container detail**: "Voyage details" shows 11 rows, **8 of them em-dashes**.
- **Shipment detail**: "Consignee & route" opens with four consecutive dashes.

A person opening a container wants to know where it is. They are instead handed
a mostly-empty table and asked to find the three rows that say something. The
screen is doing the database's job of listing columns rather than the product's
job of answering a question.

**This is the highest-leverage change in the app and it is one component.**

### What to do

1. Give `DataRow` a `hideEmpty` prop, defaulting to **true** for detail views.
2. Give `DataList` an `emptyCount` awareness: if a whole section has no values,
   render the section as a single muted line — "No voyage details recorded yet"
   — with an **Add details** action, rather than a list of dashes.
3. Keep the em-dash behaviour **only** where the surface genuinely is a form
   being filled in. Pass `hideEmpty=false` explicitly there, so the exception is
   visible at the call site.

Do not solve this by deleting fields from the DocType. The data is legitimate;
the display is what is wrong.

---

## 1. The list screens: three rows of chrome, three redundant columns

### What is wrong now

On `/containers` (both phone and desktop) the user meets, in order:

1. a page title,
2. a **New container** button,
3. a pill row: **All / Imports / Exports**,
4. a search box,
5. a **second** pill row: **All / Active / Completed / Cancelled**,
6. then, finally, data.

Two of those pill rows both begin with a button labelled **All**, meaning two
different things on one screen.

Then the desktop table has six columns, and three of them carry no information:

| Column | Problem |
|---|---|
| `ROUTE` | Contains a badge reading "Import" — not a route. It never varies inside a filtered view, and duplicates the Imports/Exports pills directly above it. A route is "Shanghai → Tema". |
| `STATUS` | "Active" on every row, duplicating the Active/Completed pills above it. |
| `SHIPMENTS` | "1" on every row. |

Each row also stacks two identifiers — `MNBU0367216` over `CONT-2026-00002`.
The first is the real container number a person quotes on the phone; the second
is an internal name.

### What to do

- **Collapse the two pill rows into one control.** Direction and status are
  both filters; they should not be two competing bars. Use one row of status
  pills and move direction into a small segmented control or a dropdown beside
  the search. Never render two buttons labelled "All".
- **Drop the `ROUTE` column** or make it show an actual route
  (`origin → destination`). If the data is not there yet, drop it.
- **Drop `STATUS` as a column** when a status filter is active; keep the badge
  on the row identifier instead.
- **Drop `SHIPMENTS`** unless the number varies. A column that is always "1" is
  a column that should be a detail-page fact.
- **Show one identifier.** Lead with the container number. The internal name
  belongs on the detail page, or in small muted text only when it differs
  meaningfully.

Apply the same review to `/shipments`, `/dispatch`, `/customers`, `/billing`.
For each list, answer in a comment at the top of the file: *what question does
someone open this screen to answer?* Then keep only the columns that answer it.

---

## 2. Detail screens: duplicated status, duplicated actions

`ContainerDetail.vue` currently shows the status **three times**:

- an `Active` badge beside the title,
- a **Status** button in the header,
- a **Current status** card repeating "In Transit / Active" with its own
  **Update** button.

Two buttons do the same job. Two badges say the same word.

`ShipmentDetail.vue` (780 lines, the largest file in the app) does the same, and
adds a **Profit & Loss** panel showing `+0.00` with `0 invoice(s)` and
`0 purchase(s)` — a prominent black card reporting that nothing has happened.

### What to do

- **One status, one place, one action.** Keep the badge next to the title and
  make it the control — tapping it opens the status sheet. Delete the separate
  Status button and the Current status card.
- **Hide panels with nothing in them.** The P&L card should not render until
  there is at least one invoice or purchase. Replace it with a single quiet
  line and the two record actions, or nothing at all.
- **`ShipmentDetail.vue` at 780 lines is doing too much.** Split it: the header,
  each section, and the status sheet are separate components. Do this only after
  the sections above are correct, or you will carefully modularise screens that
  should not exist.

---

## 3. The dashboard reports mostly nothing

Seven stat tiles, **five reading `0.00`**. Two charts with no data. Three panels
saying "Nothing due this week", "No invoices yet this month", "No payments yet".

A new operator's first impression of the product is a wall of zeros.

### What to do

- **Collapse the five money tiles into one card** with a small breakdown, or
  hide the ones that are zero behind a "show all" affordance.
- **Charts with no data should not render an empty axis.** Show a single line —
  "Revenue will appear here once you raise an invoice" — with the action that
  creates the first one.
- **Empty panels should merge.** Three cards each saying "nothing" is worse than
  one card saying "nothing has happened this week yet."
- The dashboard should answer: *what needs me today?* Lead with anything
  overdue, arriving, or stuck. Money summaries come second.

---

## 4. Architecture: what should and should not show, decided in one place

The app has **18 DocTypes** and **122 whitelisted API functions** across 19
modules in `bwm_logistics/api/`. The list and detail screens each decide their
own columns and sections inline. That is why the redundancy above appears
independently on several screens — there is no single statement of what matters.

### What to do

Create **one module that states, per entity, what a person needs to see** — for
example `frontend/src/lib/views.ts`:

```ts
// What each entity shows, and where. One statement, so a column that stops
// earning its place is removed once rather than on four screens.
export const CONTAINER_VIEW = {
  list: ["container_no", "milestone", "eta"],        // answers "where is it?"
  detail: {
    "Voyage":   ["shipping_line", "vessel", "master_bl", "etd", "eta"],
    "Customs":  ["customs_status", "free_days", "demurrage_from"],
  },
  hideWhenEmpty: true,
};
```

Then drive `DataTable` and `DataList` from it. The test in §6 asserts the
screens match this file, so the two cannot drift.

---

## 5. What must NOT show when something is selected

The brief asked specifically about this. State these rules and enforce them:

- **When a status filter is active**, the status column disappears — every row
  has that status by definition.
- **When Imports is selected**, the direction badge disappears from the rows.
- **When a container has no shipments**, the shipments panel does not render an
  empty table; it renders one line and the action to add one.
- **When a shipment is Own Goods**, consignee/receiver fields do not render —
  there is no customer to consign to. When it is Customer Cargo, the P&L panel
  does not render — it is not your margin.
- **When a container is Completed**, "Update status" is not the primary action.
- **On the customer portal**, nothing about cost, margin, purchase or supplier
  ever renders. Audit `frontend/src/pages/portal/` against this and prove it in
  a test — this is a data-leak class of bug, not a design preference.

---

## 6. Tests to run — and the ones that will actually catch something

`yarn shots` already exists and does more than most projects have. Extend it:

1. **An em-dash budget.** For every detail route, fail if more than **25 %** of
   rendered `DataRow`s show an em-dash. This is the test that would have caught
   the finding at the top of this document, and it is cheap.

2. **A column-value test.** For each list screen, using the existing
   `populated.spec.ts` fixtures, fail if any column renders the **same value in
   every row** across ≥5 rows. That is the `ROUTE`/`STATUS`/`SHIPMENTS` bug,
   caught automatically and permanently.

3. **A portal leak test.** Load every `/portal/*` route with a fixture whose
   payload deliberately includes `cost`, `margin`, `supplier` and
   `purchase_total`, and assert none of those strings appear in the DOM. Then
   assert the same at the API layer — that the portal endpoints never return
   those keys, regardless of what the frontend does with them.

4. **A first-run test.** Point every screen at empty fixtures and screenshot.
   Every empty state must name the next action. Fail on the bare words "No data"
   or an empty table with headers.

5. **A duplicate-control test.** On each detail route, fail if two controls
   carry the same accessible name (the Status/Update duplication).

6. **Backend: one round of junk.** For each of the ~122 API functions that takes
   a document name, call it with a name belonging to another customer and assert
   it refuses. In a multi-tenant logistics app this is the equivalent of the
   permission flight — write it once and run it on every change.

---

## How to verify you have finished

Run `yarn shots` and compare against `frontend/tests/__shots__/` as it stands
today. The new screenshots should show, at every width:

- fewer rows on detail pages, and **no runs of consecutive em-dashes**,
- one filter bar per list, never two, and never two buttons labelled "All",
- no column whose value is identical in every row,
- no card whose entire content is a zero or the word "No",
- the same information reachable in the same or fewer taps.

If a screen got *longer*, something has gone wrong.

---

## Two things to be careful about

**Do not delete data or DocType fields to make screens shorter.** Every problem
above is a display decision. The container's `demurrage_from` matters enormously
on the day it matters; it just should not occupy a row saying "—" on every other
day.

**Do not turn this into a redesign.** The visual language — gold/black/white,
the card and pill vocabulary, the four bottom tabs — is fine and consistent.
The problem is quantity, not style. Changing the palette would be a way of
avoiding the actual work.
