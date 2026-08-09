// What each entity shows, and where.
//
// The list and detail screens used to decide their own columns and sections
// inline, which is why the same redundancy — a column repeating the filter
// above it, a section of em-dashes — appeared independently on four screens.
// One statement here instead, so a field that stops earning its place is
// removed once. `views.spec.ts` asserts the screens still match this file.
//
// The rule for a list column is narrow on purpose: **it must be able to differ
// between two rows the user is currently looking at.** A column that repeats
// the active filter, or that reads "1" all the way down, is decoration.

import type { Column } from "@/components/ui/DataTable.vue";

export interface ViewColumn extends Column {
	/**
	 * Drop the column when no row on screen can fill it. Route is the case
	 * this exists for: real once ports are recorded, an empty strip until then.
	 */
	showWhen?: (rows: Record<string, unknown>[]) => boolean;
}

/** Columns that only earn their place when a filter is NOT pinning them. */
export interface ListView {
	/** The question this screen exists to answer. Shown nowhere; kept honest by review. */
	question: string;
	columns: ViewColumn[];
	/**
	 * Columns to drop while the named filter is active, because every visible
	 * row then carries the same value by definition.
	 */
	redundantWhen?: Record<string, string[]>;
}

const some = (key: string) => (rows: Record<string, unknown>[]) => rows.some((r) => !!r[key]);

export const CONTAINER_LIST: ListView = {
	question: "Which boxes need me today, and where are they?",
	columns: [
		{ key: "container_no", label: "Container", primary: true },
		{ key: "risk", label: "", trailing: true, showWhen: some("at_risk") },
		{ key: "status", label: "Status", trailing: true },
		{
			key: "route",
			label: "Route",
			showWhen: (rows) => rows.some((r) => r.port_of_loading || r.port_of_discharge),
		},
		{ key: "current_milestone", label: "Milestone" },
		{ key: "eta", label: "ETA", nowrap: true },
	],
	redundantWhen: { status: ["status"] },
};

export const SHIPMENT_LIST: ListView = {
	question: "Whose cargo is where, and what is it worth?",
	columns: [
		{ key: "name", label: "Tracking No", primary: true, nowrap: true },
		{ key: "status", label: "Status", trailing: true },
		{ key: "customer_name", label: "Customer" },
		{ key: "destination", label: "Destination" },
		{ key: "container", label: "Container" },
		{ key: "total_charges", label: "Charges", numeric: true },
	],
	redundantWhen: { status: ["status"], direction: ["direction"] },
};

export const DISPATCH_LIST: ListView = {
	question: "Which runs are out, who is driving them, and is the cash back?",
	columns: [
		{ key: "name", label: "Run", primary: true },
		{ key: "status", label: "Status", trailing: true },
		{ key: "driver_name", label: "Driver" },
		{ key: "run_date", label: "Date", nowrap: true },
		{ key: "stops", label: "Stops", numeric: true },
		{ key: "cod", label: "COD", numeric: true },
	],
	redundantWhen: { status: ["status"] },
};

export const CUSTOMER_LIST: ListView = {
	question: "Who are they, how do I reach them, and can they see their portal?",
	columns: [
		{ key: "customer_name", label: "Customer", primary: true },
		{ key: "statement", label: "", class: "w-28", trailing: true },
		{ key: "mobile_no", label: "Phone", nowrap: true },
		{ key: "email_id", label: "Email" },
		{ key: "portal_user", label: "Portal access" },
	],
};

/**
 * Drop the columns a live filter has made constant.
 *
 * `active` maps a filter name to its current value — an empty string meaning
 * "All", which pins nothing.
 */
export function columnsFor(
	view: ListView,
	active: Record<string, string> = {},
	rows: Record<string, unknown>[] = [],
): Column[] {
	const drop = new Set<string>();
	for (const [filter, keys] of Object.entries(view.redundantWhen || {})) {
		if (active[filter]) keys.forEach((k) => drop.add(k));
	}
	return view.columns.filter((c) => {
		if (drop.has(c.key)) return false;
		// A column nothing on screen can fill is a header with a blank strip
		// under it. Keep it only once a row has something to put there.
		if (c.showWhen && rows.length && !c.showWhen(rows)) return false;
		return true;
	});
}
