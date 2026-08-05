import type { Page } from "@playwright/test";

// Canned API responses for the UI audit.
//
// The dev site is usually empty (or holds real client data), and neither state
// shows what a busy list actually looks like. Rather than seed the database,
// the populated screenshot pass intercepts `POST /api/method/<whitelisted>`
// and answers from here — so the layout is exercised against long names, wide
// figures and full tables without a single row being written anywhere.
//
// Keys are Frappe dotted method paths; values are what `call()` unwraps from
// `{ message: … }`. Anything not listed falls through to the real server.

const CUSTOMERS = [
	{
		name: "CUST-0001",
		customer_name: "Akosua Mensah-Boateng Enterprise",
		mobile_no: "+233 20 111 2233",
		email_id: "akosua.mensah@longishdomainname.com.gh",
		shipment_count: 42,
		portal_user: "akosua@example.com",
	},
	{
		name: "CUST-0002",
		customer_name: "Kofi Trading Co.",
		mobile_no: "+233 24 555 0199",
		email_id: "kofi@kofitrading.gh",
		shipment_count: 17,
		portal_user: null,
	},
	{
		name: "CUST-0003",
		customer_name: "Adjei & Sons Logistics Limited",
		mobile_no: "+233 27 909 8877",
		email_id: "ops@adjeiandsons.com",
		shipment_count: 8,
		portal_user: null,
	},
	{
		name: "CUST-0004",
		customer_name: "Ama Serwaa",
		mobile_no: "+233 55 400 1122",
		email_id: "ama.serwaa@mail.com",
		shipment_count: 3,
		portal_user: "ama.serwaa@mail.com",
	},
	{
		name: "CUST-0005",
		customer_name: "Tema Harbour Freight Forwarders",
		mobile_no: "+233 30 220 4400",
		email_id: "desk@temaharbourfreight.com.gh",
		shipment_count: 129,
		portal_user: null,
	},
];

const SHIPMENTS = [
	{
		name: "BWM-000148",
		customer_name: "Akosua Mensah-Boateng Enterprise",
		direction: "Import",
		status: "In Transit",
		container: "MSKU-778812-3",
		destination: "Kumasi — Adum",
		total_charges: 18450,
		current_milestone: "Vessel departed",
		shipment_type: "Customer Goods",
	},
	{
		name: "BWM-000147",
		customer_name: "Kofi Trading Co.",
		direction: "Import",
		status: "Arrived",
		container: "TCLU-990021-8",
		destination: "Accra — Osu",
		total_charges: 7320.5,
		current_milestone: "Arrived",
		shipment_type: "Customer Goods",
	},
	{
		name: "BWM-000146",
		customer_name: null,
		direction: "Export",
		status: "Ready for Delivery",
		container: null,
		destination: "Takoradi",
		total_charges: 43900,
		current_milestone: "Delayed",
		shipment_type: "Own Goods (Trading)",
	},
	{
		name: "BWM-000145",
		customer_name: "Tema Harbour Freight Forwarders",
		direction: "Import",
		status: "Delivered",
		container: "MSKU-112233-9",
		destination: "Tema — Community 25",
		total_charges: 2100,
		current_milestone: "Delivered",
		shipment_type: "Customer Goods",
	},
	{
		name: "BWM-000144",
		customer_name: "Adjei & Sons Logistics Limited",
		direction: "Export",
		status: "Open",
		container: null,
		destination: "Rotterdam",
		total_charges: 96500,
		current_milestone: "Booked",
		shipment_type: "Customer Goods",
	},
];

const CONTAINERS = [
	{
		name: "CON-0031",
		container_no: "MSKU-778812-3",
		direction: "Import",
		status: "Active",
		current_milestone: "Vessel departed",
		eta: "2026-08-14",
		shipment_count: 12,
	},
	{
		name: "CON-0030",
		container_no: "TCLU-990021-8",
		direction: "Import",
		status: "Active",
		current_milestone: "Arrived",
		eta: "2026-08-07",
		shipment_count: 31,
	},
	{
		name: "CON-0029",
		container_no: "MSKU-112233-9",
		direction: "Export",
		status: "Completed",
		current_milestone: "Delivered",
		eta: "2026-07-28",
		shipment_count: 4,
	},
];

const INVOICES = [
	{
		name: "ACC-SINV-2026-00231",
		customer_name: "Akosua Mensah-Boateng Enterprise",
		posting_date: "2026-08-01",
		status: "Overdue",
		grand_total: 18450,
		outstanding_amount: 18450,
		currency: "GHS",
		shipment: "BWM-000148",
	},
	{
		name: "ACC-SINV-2026-00230",
		customer_name: "Kofi Trading Co.",
		posting_date: "2026-07-29",
		status: "Unpaid",
		grand_total: 7320.5,
		outstanding_amount: 3200,
		currency: "GHS",
		shipment: "BWM-000147",
	},
	{
		name: "ACC-SINV-2026-00229",
		customer_name: "Tema Harbour Freight Forwarders",
		posting_date: "2026-07-24",
		status: "Paid",
		grand_total: 2100,
		outstanding_amount: 0,
		currency: "GHS",
		shipment: null,
	},
];

const months = [
	"Sep",
	"Oct",
	"Nov",
	"Dec",
	"Jan",
	"Feb",
	"Mar",
	"Apr",
	"May",
	"Jun",
	"Jul",
	"Aug",
];
const revenueMonths = months.map((label, i) => ({
	month: `2025-${i + 1}`,
	label,
	invoiced: 40000 + i * 6500,
	collected: 31000 + i * 5200,
}));
const shipmentMonths = months.map((label, i) => ({
	month: `2025-${i + 1}`,
	label,
	imports: 12 + ((i * 5) % 19),
	exports: 4 + ((i * 3) % 11),
}));

export const RESPONSES: Record<string, unknown> = {
	"bwm_logistics.api.dashboard.get_overview": {
		revenue_mtd: 184_500,
		collected_mtd: 121_300,
		outstanding_total: 96_240,
		overdue_count: 7,
		containers_active: 14,
		containers_import: 11,
		containers_export: 3,
		shipments_active: 63,
		shipments_import: 48,
		shipments_export: 15,
		pipeline: [
			{ status: "Open", count: 12 },
			{ status: "In Transit", count: 26 },
			{ status: "Arrived", count: 15 },
			{ status: "Ready for Delivery", count: 10 },
		],
		demurrage_risk: [
			{ name: "CON-0031", container_no: "MSKU-778812-3", days_left: 2 },
			{ name: "CON-0030", container_no: "TCLU-990021-8", days_left: 0 },
		],
		cod_unreconciled: 4_820,
		arriving_week: [
			{
				name: "CON-0031",
				container_no: "MSKU-778812-3",
				eta: "2026-08-07",
				vessel: "MAERSK KOWLOON",
				port_of_discharge: "Tema",
				direction: "Import",
			},
			{
				name: "CON-0032",
				container_no: "OOLU-445566-1",
				eta: "2026-08-09",
				vessel: "OOCL SOUTHAMPTON",
				port_of_discharge: "Takoradi",
				direction: "Import",
			},
		],
		top_customers: [
			{ customer: "Tema Harbour Freight Forwarders", total: 61_200 },
			{ customer: "Akosua Mensah-Boateng Enterprise", total: 44_800 },
			{ customer: "Adjei & Sons Logistics Limited", total: 18_150 },
		],
		recent_payments: [
			{
				name: "PAY-0091",
				posting_date: "2026-08-04",
				party_name: "Kofi Trading Co.",
				paid_amount: 4_120,
				mode_of_payment: "Mobile Money",
			},
			{
				name: "PAY-0090",
				posting_date: "2026-08-03",
				party_name: "Tema Harbour Freight Forwarders",
				paid_amount: 22_000,
				mode_of_payment: "Bank Transfer",
			},
		],
		revenue_months: revenueMonths,
		shipment_months: shipmentMonths,
		recent_events: [
			{
				name: "TE-0501",
				event_datetime: "2026-08-05 09:14:00",
				milestone: "Vessel departed",
				location: "Port of Shanghai",
				container: "CON-0031",
				shipment: null,
			},
			{
				name: "TE-0500",
				event_datetime: "2026-08-04 17:40:00",
				milestone: "Out for delivery",
				location: "Accra — Osu",
				container: null,
				shipment: "BWM-000147",
			},
			{
				name: "TE-0499",
				event_datetime: "2026-08-04 11:02:00",
				milestone: "Customs cleared",
				location: "Tema Port",
				container: "CON-0030",
				shipment: null,
			},
		],
		stock_on_hand: {
			product_count: 2,
			products: [
				{
					product: "Frozen mackerel 20kg cartons",
					unit: "Cartons",
					remaining: 1_240,
				},
				{ product: "Rice — 50kg bags", unit: "Bags", remaining: 310 },
			],
		},
		profit_mtd: 63_200,
		spent_mtd: 121_300,
	},
	"bwm_logistics.api.customers.list_customers": {
		rows: CUSTOMERS,
		total: CUSTOMERS.length,
	},
	"bwm_logistics.api.shipments.list_shipments": {
		rows: SHIPMENTS,
		total: SHIPMENTS.length,
	},
	"bwm_logistics.api.containers.list_containers": {
		rows: CONTAINERS,
		total: CONTAINERS.length,
	},
	"bwm_logistics.api.billing.list_invoices": {
		rows: INVOICES,
		total: INVOICES.length,
	},
	"bwm_logistics.api.billing.overview": {
		unpaid_total: 96_240,
		unpaid_count: 11,
		overdue_count: 7,
		collected_this_month: 121_300,
		uninvoiced: [
			{
				name: "BWM-000146",
				customer_name: "Adjei & Sons Logistics Limited",
				total_charges: 43_900,
			},
			{
				name: "BWM-000144",
				customer_name: "Tema Harbour Freight Forwarders",
				total_charges: 96_500,
			},
		],
	},
	"bwm_logistics.api.dispatch.list_runs": {
		rows: [
			{
				name: "RUN-0042",
				run_date: "2026-08-05",
				driver_name: "Yaw Boakye",
				status: "In Progress",
				completed_stops: 4,
				total_stops: 11,
				cod_collected_total: 2_400,
			},
			{
				name: "RUN-0041",
				run_date: "2026-08-04",
				driver_name: "Emmanuel Nii Armah",
				status: "Completed",
				completed_stops: 9,
				total_stops: 9,
				cod_collected_total: 6_150,
			},
		],
		total: 2,
	},
};

/**
 * Serve `RESPONSES` for any matching whitelisted call; everything else hits
 * the real bench. Install before `page.goto`.
 */
export async function useFixtures(page: Page) {
	await page.route("**/api/method/**", async (route) => {
		const method = decodeURIComponent(
			route.request().url().split("/api/method/")[1] || "",
		);
		if (method in RESPONSES) {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ message: RESPONSES[method] }),
			});
			return;
		}
		await route.fallback();
	});
}
