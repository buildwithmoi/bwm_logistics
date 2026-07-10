<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { Plus, Search, Users, Mail, CheckCircle2 } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Dialog from "@/components/ui/Dialog.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";

const toast = useToast();
const session = useSessionStore();

// ── list ────────────────────────────────────────────────────────────────────
interface Row extends Record<string, unknown> {
	name: string;
	customer_name: string;
	mobile_no?: string;
	email_id?: string;
	shipment_count: number;
	portal_user?: string | null;
}
const rows = ref<Row[]>([]);
const total = ref(0);
const loading = ref(false);
const search = ref("");
const PAGE = 25;

async function load(append = false) {
	loading.value = true;
	try {
		const res = await call<{ rows: Row[]; total: number }>(
			"bwm_logistics.api.customers.list_customers",
			{ search: search.value || null, start: append ? rows.value.length : 0, limit: PAGE },
		);
		rows.value = append ? [...rows.value, ...res.rows] : res.rows;
		total.value = res.total;
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load customers");
	} finally {
		loading.value = false;
	}
}
let searchTimer: ReturnType<typeof setTimeout>;
watch(search, () => {
	clearTimeout(searchTimer);
	searchTimer = setTimeout(() => load(), 300);
});
onMounted(load);

const columns: Column[] = [
	{ key: "customer_name", label: "Customer" },
	{ key: "mobile_no", label: "Phone" },
	{ key: "email_id", label: "Email" },
	{ key: "shipment_count", label: "Shipments", numeric: true },
	{ key: "portal_user", label: "Portal access" },
];

// ── create dialog ───────────────────────────────────────────────────────────
const createOpen = ref(false);
const saving = ref(false);
const canWrite = computed(() => session.can("customers", "create"));
const form = reactive({ customer_name: "", mobile_no: "", email_id: "", invite: true });

async function save() {
	if (!form.customer_name) {
		toast.warning("Customer name is required");
		return;
	}
	if (form.invite && !form.email_id) {
		toast.warning("An email is needed to send the portal invitation");
		return;
	}
	saving.value = true;
	try {
		const res = await call<{ name: string }>("bwm_logistics.api.customers.save_customer", {
			payload: { customer_name: form.customer_name, mobile_no: form.mobile_no, email_id: form.email_id },
		});
		if (form.invite && form.email_id) {
			await call("bwm_logistics.api.customers.invite_portal_user", {
				customer: res.name,
				email: form.email_id,
			});
			toast.success("Customer created — set-password email sent");
		} else {
			toast.success("Customer created");
		}
		createOpen.value = false;
		form.customer_name = "";
		form.mobile_no = "";
		form.email_id = "";
		await load();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not save customer");
	} finally {
		saving.value = false;
	}
}

// ── invite (from row) ───────────────────────────────────────────────────────
const inviteFor = ref<Row | null>(null);
const inviteEmail = ref("");
const inviting = ref(false);
function openInvite(row: Row) {
	inviteFor.value = row;
	inviteEmail.value = row.email_id || "";
}
async function sendInvite() {
	if (!inviteFor.value) return;
	inviting.value = true;
	try {
		await call("bwm_logistics.api.customers.invite_portal_user", {
			customer: inviteFor.value.name,
			email: inviteEmail.value,
		});
		toast.success("Invitation sent — the customer sets their own password");
		inviteFor.value = null;
		await load();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not send invitation");
	} finally {
		inviting.value = false;
	}
}
</script>

<template>
	<div class="mx-auto max-w-6xl">
		<header class="mb-5 flex flex-wrap items-center gap-3">
			<h1 class="min-w-0 flex-1 text-2xl font-semibold tracking-tight">Customers</h1>
			<Button v-if="canWrite" @click="createOpen = true"><Plus class="h-4 w-4" /> New customer</Button>
		</header>

		<div class="mb-4">
			<div class="relative max-w-xs">
				<Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
				<Input v-model="search" placeholder="Search name, phone, email…" class="pl-9" />
			</div>
		</div>

		<DataTable
			:columns="columns"
			:rows="rows"
			:loading="loading"
			:total="total"
			empty-text="No customers yet."
			@load-more="load(true)"
		>
			<template #cell-customer_name="{ row }">
				<div class="flex items-center gap-2.5 font-medium">
					<span class="flex h-8 w-8 items-center justify-center rounded-full bg-brand-600/10 text-xs font-bold text-brand-700">
						{{ String(row.customer_name)[0]?.toUpperCase() }}
					</span>
					{{ row.customer_name }}
				</div>
			</template>
			<template #cell-portal_user="{ row }">
				<span v-if="row.portal_user" class="inline-flex items-center gap-1.5 text-[13px] text-emerald-700">
					<CheckCircle2 class="h-3.5 w-3.5" /> {{ row.portal_user }}
				</span>
				<button
					v-else-if="canWrite"
					type="button"
					class="inline-flex items-center gap-1.5 text-[13px] font-medium text-brand-700 hover:underline"
					@click.stop="openInvite(row as Row)"
				>
					<Mail class="h-3.5 w-3.5" /> Invite to portal
				</button>
				<span v-else class="text-gray-400">—</span>
			</template>
		</DataTable>

		<!-- ── New customer ──────────────────────────────────────────────── -->
		<Dialog v-model:open="createOpen" title="New customer">
			<div class="space-y-4">
				<div class="space-y-1.5">
					<Label required>Full name</Label>
					<Input v-model="form.customer_name" placeholder="e.g. Ama Mensah" />
				</div>
				<div class="space-y-1.5">
					<Label>Phone (for SMS updates)</Label>
					<Input v-model="form.mobile_no" placeholder="+233…" />
				</div>
				<div class="space-y-1.5">
					<Label>Email</Label>
					<Input v-model="form.email_id" type="email" placeholder="customer@example.com" />
				</div>
				<label class="flex cursor-pointer items-center gap-2.5 rounded-xl bg-brand-50 px-4 py-3">
					<input v-model="form.invite" type="checkbox" class="h-4 w-4 rounded accent-[#b8860b]" />
					<span class="text-sm">
						<span class="font-medium">Invite to the customer portal</span>
						<span class="block text-xs text-muted-foreground">
							They'll receive an email with a link to set their own password
						</span>
					</span>
				</label>
			</div>
			<template #footer>
				<div class="flex justify-end gap-2">
					<Button variant="outline" @click="createOpen = false">Cancel</Button>
					<Button :loading="saving" @click="save">Create customer</Button>
				</div>
			</template>
		</Dialog>

		<!-- ── Invite existing ───────────────────────────────────────────── -->
		<Dialog :open="!!inviteFor" title="Invite to customer portal" @update:open="inviteFor = null">
			<div class="space-y-4">
				<p class="text-sm text-muted-foreground">
					<b>{{ inviteFor?.customer_name }}</b> will receive an email with a link to set
					their own password, then they can track shipments and pay invoices online.
				</p>
				<div class="space-y-1.5">
					<Label required>Email</Label>
					<Input v-model="inviteEmail" type="email" placeholder="customer@example.com" />
				</div>
			</div>
			<template #footer>
				<div class="flex justify-end gap-2">
					<Button variant="outline" @click="inviteFor = null">Cancel</Button>
					<Button :loading="inviting" @click="sendInvite"><Mail class="h-4 w-4" /> Send invitation</Button>
				</div>
			</template>
		</Dialog>
	</div>
</template>
