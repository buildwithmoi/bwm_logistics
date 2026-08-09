import { createRouter, createWebHistory } from "vue-router";
import { useSessionStore } from "@/stores/session";

// SPA routes mounted under `/logistics/...` (the Frappe www path that loads
// the bundle). Two route trees share one bundle:
//   - Operator app at the root (staff roles)
//   - Customer portal under /portal (Logistics Customer role)
// Route names double as access-page keys (api/access.py PAGES).

const routes = [
	// ── Operator app ──────────────────────────────────────────────────────────
	{ path: "/", name: "dashboard", component: () => import("@/pages/Dashboard.vue") },
	{ path: "/containers", name: "containers", component: () => import("@/pages/Containers.vue") },
	// Create screens are pages, not dialogs — anything with more than a handful
	// of fields gets its own URL. Declared before the :name routes so "new" can
	// never be read as a record id.
	{ path: "/containers/new", name: "container-new", component: () => import("@/pages/ContainerNew.vue") },
	{
		path: "/containers/:name",
		name: "container-detail",
		component: () => import("@/pages/ContainerDetail.vue"),
	},
	// Editing reuses the create page — same form, loaded with the record.
	{
		path: "/containers/:name/edit",
		name: "container-edit",
		component: () => import("@/pages/ContainerNew.vue"),
	},
	{ path: "/shipments", name: "shipments", component: () => import("@/pages/Shipments.vue") },
	{ path: "/shipments/new", name: "shipment-new", component: () => import("@/pages/ShipmentNew.vue") },
	{
		path: "/shipments/:name",
		name: "shipment-detail",
		component: () => import("@/pages/ShipmentDetail.vue"),
	},
	{
		path: "/shipments/:name/edit",
		name: "shipment-edit",
		component: () => import("@/pages/ShipmentNew.vue"),
	},
	{
		path: "/shipments/:name/label",
		name: "shipment-label",
		component: () => import("@/pages/ShipmentLabel.vue"),
	},
	{ path: "/stock", name: "stock", component: () => import("@/pages/Stock.vue") },
	{ path: "/items", name: "items", component: () => import("@/pages/Items.vue") },
	{ path: "/dispatch", name: "dispatch", component: () => import("@/pages/Dispatch.vue") },
	{ path: "/dispatch/new", name: "dispatch-run-new", component: () => import("@/pages/DispatchRunNew.vue") },
	{
		path: "/dispatch/:name",
		name: "dispatch-run",
		component: () => import("@/pages/DispatchRunDetail.vue"),
	},
	{ path: "/customers", name: "customers", component: () => import("@/pages/Customers.vue") },
	{
		path: "/customers/:name/statement",
		name: "customer-statement",
		component: () => import("@/pages/CustomerStatement.vue"),
	},
	{ path: "/billing", name: "billing", component: () => import("@/pages/Billing.vue") },
	{ path: "/billing/invoice/new", name: "invoice-new", component: () => import("@/pages/InvoiceNew.vue") },
	{ path: "/billing/purchase/new", name: "purchase-new", component: () => import("@/pages/PurchaseNew.vue") },
	{
		path: "/billing/receipt/:name",
		name: "billing-receipt",
		component: () => import("@/pages/ReceiptPrint.vue"),
	},
	{ path: "/reports", name: "reports", component: () => import("@/pages/Reports.vue") },
	{
		path: "/notifications",
		name: "notifications",
		component: () => import("@/pages/NotificationsLog.vue"),
	},
	{ path: "/settings", name: "settings", component: () => import("@/pages/Settings.vue") },

	// ── Customer portal ───────────────────────────────────────────────────────
	{ path: "/portal", name: "portal", component: () => import("@/pages/portal/PortalHome.vue") },
	{
		path: "/portal/shipments",
		name: "portal-shipments",
		component: () => import("@/pages/portal/PortalShipments.vue"),
	},
	{
		path: "/portal/shipments/:name",
		name: "portal-shipment-detail",
		component: () => import("@/pages/portal/PortalShipmentDetail.vue"),
	},
	{
		path: "/portal/pickups",
		name: "portal-pickups",
		component: () => import("@/pages/portal/PortalPickups.vue"),
	},
	{
		path: "/portal/statement",
		name: "portal-statement",
		component: () => import("@/pages/portal/PortalStatement.vue"),
	},
	{
		path: "/portal/invoices",
		name: "portal-invoices",
		component: () => import("@/pages/portal/PortalInvoices.vue"),
	},
	{
		path: "/portal/profile",
		name: "portal-profile",
		component: () => import("@/pages/portal/PortalProfile.vue"),
	},

	// Unknown paths fall back to the dashboard route guard, which re-routes
	// customers to the portal.
	{ path: "/:rest(.*)*", name: "wip", redirect: { name: "dashboard" } },
];

export const router = createRouter({
	history: createWebHistory("/logistics"),
	routes,
});

// Sub-pages that inherit a parent page's access key.
const ACCESS_ALIAS: Record<string, string> = {
	"container-detail": "containers",
	"container-new": "containers",
	"container-edit": "containers",
	"shipment-detail": "shipments",
	"shipment-label": "shipments",
	"shipment-new": "shipments",
	"shipment-edit": "shipments",
	"dispatch-run": "dispatch",
	"dispatch-run-new": "dispatch",
	"customer-statement": "customers",
	"billing-receipt": "billing",
	"invoice-new": "billing",
	"purchase-new": "billing",
	"portal-shipment-detail": "portal-shipments",
	"portal-statement": "portal-invoices",
};

// Preferred landing order when a navigation is denied — first allowed wins.
const FALLBACK_ORDER = [
	"dashboard",
	"containers",
	"shipments",
	"stock",
	"dispatch",
	"billing",
	"portal",
	"portal-shipments",
];

// Per-role page access. Until access loads (allowedPages null), everything is
// allowed so first paint isn't blocked; once loaded, navigations to a page the
// role can't see are redirected to their first allowed page. (Backend APIs
// enforce their own permissions regardless — this is UX, not the security gate.)
router.beforeEach(async (to) => {
	const session = useSessionStore();
	const name = to.name as string | undefined;
	const key = name ? ACCESS_ALIAS[name] || name : undefined;
	if (!key) return true;
	// Make sure access is loaded BEFORE deciding — otherwise a fresh login lands
	// on "/" (Dashboard) before the allow-list arrives and the page leaks through.
	if (!session.allowedPages) await session.loadAccess();
	if (!session.allowedPages) return true; // guest / not loaded → let login handle it
	if (session.canSee(key)) return true;
	const first =
		FALLBACK_ORDER.find((k) => session.canSee(k)) ??
		([...session.allowedPages][0] as string | undefined);
	return first && first !== key ? { name: first } : true;
});
