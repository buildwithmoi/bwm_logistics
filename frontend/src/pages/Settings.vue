<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { Save, Copy, UserPlus, ShieldCheck, Plus, Trash2, GitBranch } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Select from "@/components/ui/Select.vue";
import Textarea from "@/components/ui/Textarea.vue";
import Dialog from "@/components/ui/Dialog.vue";

// Settings (P7): left-rail section list (same pattern as Reports) — pick a
// section on the left, its panel renders on the right. One Save covers the
// form-backed sections; Branches and Staff & Roles save through their own APIs.
const toast = useToast();
const session = useSessionStore();
const canEdit = session.hasRole("Logistics Manager", "System Manager", "Administrator");

const SECTIONS = [
	{ key: "branding", label: "Branding" },
	{ key: "website", label: "Website" },
	{ key: "tracking", label: "Tracking" },
	{ key: "notifications", label: "Notifications" },
	{ key: "branches", label: "Branches" },
	{ key: "staff", label: "Staff & Roles", managed: true },
] as const;
type SectionKey = (typeof SECTIONS)[number]["key"];
const section = ref<SectionKey>("branding");
const sections = computed(() => SECTIONS.filter((s) => !("managed" in s && s.managed) || canEdit));
// Save applies to the Logistics Settings-backed panels only.
const showSave = computed(() => !["branches", "staff"].includes(section.value));

interface SettingsData extends Record<string, unknown> {
	business_name?: string;
	tracking_prefix?: string;
	tracking_provider?: string;
	tracking_webhook_token?: string;
	tracking_api_key_set?: boolean;
	whatsapp_api_token_set?: boolean;
	email_enabled?: number;
	sms_enabled?: number;
	whatsapp_enabled?: number;
	email_subject_template?: string;
	email_body_template?: string;
	sms_template?: string;
	whatsapp_gateway_url?: string;
	hero_title?: string;
	hero_subtitle?: string;
	contact_phone?: string;
	contact_email?: string;
	office_hours?: string;
}
const loading = ref(true);
const saving = ref(false);
const form = reactive<SettingsData & { tracking_api_key: string; whatsapp_api_token: string }>({
	tracking_api_key: "",
	whatsapp_api_token: "",
});

onMounted(async () => {
	try {
		Object.assign(form, await call<SettingsData>("bwm_logistics.api.settings.get_settings"));
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load settings");
	} finally {
		loading.value = false;
	}
	loadStaff();
	loadRoles();
	loadBranches();
});

// ── branches ────────────────────────────────────────────────────────────────
const branches = ref<string[]>([]);
const branchName = ref("");
const branchSaving = ref(false);
async function loadBranches() {
	try {
		branches.value = await call<string[]>("bwm_logistics.api.settings.list_branches");
	} catch {
		branches.value = [];
	}
}
async function addBranch() {
	if (!branchName.value.trim()) {
		toast.warning("Name the branch");
		return;
	}
	branchSaving.value = true;
	try {
		await call("bwm_logistics.api.settings.add_branch", { name: branchName.value.trim() });
		toast.success(`Branch "${branchName.value.trim()}" added`);
		branchName.value = "";
		await loadBranches();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not add branch");
	} finally {
		branchSaving.value = false;
	}
}

// ── staff & roles ───────────────────────────────────────────────────────────
interface StaffRow {
	name: string;
	full_name?: string;
	bwm_logistics_role?: string | null;
	is_driver?: boolean;
	is_super?: boolean;
}
interface RoleRow {
	name: string;
	role_name: string;
	is_admin: number;
	all_pages: number;
	pages: string[];
	members: number;
}
const staff = ref<StaffRow[]>([]);
const roles = ref<RoleRow[]>([]);
const pageCatalog = ref<Array<{ key: string; label: string }>>([]);

async function loadStaff() {
	try {
		staff.value = await call<StaffRow[]>("bwm_logistics.api.staff.list_staff");
	} catch {
		/* section hidden for non-managers anyway */
	}
}
async function loadRoles() {
	try {
		const res = await call<{ pages: Array<{ key: string; label: string }>; roles: RoleRow[] }>(
			"bwm_logistics.api.staff.list_roles",
		);
		pageCatalog.value = res.pages;
		roles.value = res.roles;
	} catch {
		/* ignore */
	}
}

// staff creation
const staffOpen = ref(false);
const staffSaving = ref(false);
const staffForm = reactive({ full_name: "", email: "", logistics_role: "" });
async function createStaff() {
	if (!staffForm.full_name || !staffForm.email) {
		toast.warning("Name and email are required");
		return;
	}
	staffSaving.value = true;
	try {
		await call("bwm_logistics.api.staff.create_staff", {
			full_name: staffForm.full_name,
			email: staffForm.email,
			logistics_role: staffForm.logistics_role || null,
		});
		toast.success("Staff created — set-password email sent");
		staffOpen.value = false;
		staffForm.full_name = "";
		staffForm.email = "";
		await Promise.all([loadStaff(), loadRoles()]);
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not create staff");
	} finally {
		staffSaving.value = false;
	}
}

async function changeRole(user: StaffRow, role: string) {
	try {
		await call("bwm_logistics.api.staff.assign_role", {
			user: user.name,
			logistics_role: role || null,
		});
		user.bwm_logistics_role = role || null;
		toast.success(`Role updated for ${user.full_name || user.name}`);
		await loadRoles();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not update role");
		await loadStaff();
	}
}

// role editor
const roleOpen = ref(false);
const roleSaving = ref(false);
const roleForm = reactive<{ name?: string; role_name: string; is_admin: number; all_pages: number; pages: Set<string> }>(
	{ role_name: "", is_admin: 0, all_pages: 0, pages: new Set() },
);
function openRole(role?: RoleRow) {
	Object.assign(roleForm, {
		name: role?.name,
		role_name: role?.role_name || "",
		is_admin: role?.is_admin || 0,
		all_pages: role?.all_pages || 0,
		pages: new Set(role?.pages || []),
	});
	roleOpen.value = true;
}
async function saveRole() {
	if (!roleForm.role_name.trim()) {
		toast.warning("Name the role");
		return;
	}
	roleSaving.value = true;
	try {
		await call("bwm_logistics.api.staff.save_role", {
			payload: {
				name: roleForm.name,
				role_name: roleForm.role_name,
				is_admin: roleForm.is_admin,
				all_pages: roleForm.all_pages,
				pages: [...roleForm.pages],
			},
		});
		toast.success("Role saved");
		roleOpen.value = false;
		await Promise.all([loadRoles(), loadStaff()]);
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not save role");
	} finally {
		roleSaving.value = false;
	}
}
async function deleteRole(role: RoleRow) {
	try {
		await call("bwm_logistics.api.staff.delete_role", { name: role.name });
		toast.info(`Deleted ${role.role_name}`);
		await loadRoles();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not delete role");
	}
}
function togglePage(key: string) {
	roleForm.pages.has(key) ? roleForm.pages.delete(key) : roleForm.pages.add(key);
}

async function save() {
	saving.value = true;
	try {
		await call("bwm_logistics.api.settings.save_settings", { payload: { ...form } });
		toast.success("Settings saved");
		form.tracking_api_key = "";
		form.whatsapp_api_token = "";
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not save settings");
	} finally {
		saving.value = false;
	}
}

const webhookUrl = () =>
	`${window.location.origin}/api/method/bwm_logistics.api.carrier_webhook.receive?token=${form.tracking_webhook_token || ""}`;

async function copyWebhook() {
	try {
		await navigator.clipboard.writeText(webhookUrl());
		toast.success("Webhook URL copied");
	} catch {
		toast.info(webhookUrl());
	}
}
</script>

<template>
	<div class="mx-auto max-w-5xl">
		<header class="mb-5 flex flex-wrap items-center gap-3">
			<div class="min-w-0 flex-1">
				<h1 class="text-2xl font-semibold tracking-tight">Settings</h1>
				<p class="mt-1 text-sm text-muted-foreground">Branding, website, tracking, notifications, branches and your team.</p>
			</div>
			<Button v-if="canEdit && showSave" :loading="saving" @click="save"><Save class="h-4 w-4" /> Save</Button>
		</header>

		<div v-if="loading" class="py-16 text-center text-sm text-muted-foreground">Loading…</div>
		<div v-else class="flex flex-col gap-6 lg:flex-row">
			<!-- Left rail (Reports pattern) -->
			<nav class="flex shrink-0 gap-1 overflow-x-auto lg:w-52 lg:flex-col">
				<button
					v-for="s in sections"
					:key="s.key"
					type="button"
					class="shrink-0 rounded-lg px-3.5 py-2 text-left text-sm font-medium transition-colors"
					:class="section === s.key ? 'bg-brand-50 text-brand-800' : 'text-gray-600 hover:bg-gray-50'"
					@click="section = s.key"
				>
					{{ s.label }}
				</button>
			</nav>

			<!-- Panel -->
			<div class="min-w-0 flex-1">
				<!-- Branding -->
				<section v-if="section === 'branding'" class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
					<h2 class="label-caps mb-4">Branding</h2>
					<div class="grid gap-4 sm:grid-cols-2">
						<div class="space-y-1.5">
							<Label>Business name</Label>
							<Input v-model="form.business_name" :disabled="!canEdit" placeholder="BWM Logistics" />
							<p class="text-xs text-muted-foreground">Appears on the website, notifications, and printed invoices.</p>
						</div>
						<div class="space-y-1.5">
							<Label>Tracking number prefix</Label>
							<Input v-model="form.tracking_prefix" :disabled="!canEdit" placeholder="BWM" />
							<p class="text-xs text-muted-foreground">New shipments become PREFIX-000001. Existing numbers keep their prefix.</p>
						</div>
					</div>
				</section>

				<!-- Website -->
				<section v-else-if="section === 'website'" class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
					<h2 class="label-caps mb-4">Public website</h2>
					<div class="grid gap-4">
						<div class="space-y-1.5">
							<Label>Hero title</Label>
							<Input v-model="form.hero_title" :disabled="!canEdit" placeholder="Your cargo, tracked from port to doorstep." />
						</div>
						<div class="space-y-1.5">
							<Label>Hero subtitle</Label>
							<Textarea v-model="form.hero_subtitle" :rows="2" :disabled="!canEdit" />
						</div>
						<div class="grid gap-4 sm:grid-cols-3">
							<div class="space-y-1.5">
								<Label>Phone</Label>
								<Input v-model="form.contact_phone" :disabled="!canEdit" />
							</div>
							<div class="space-y-1.5">
								<Label>Email</Label>
								<Input v-model="form.contact_email" :disabled="!canEdit" />
							</div>
							<div class="space-y-1.5">
								<Label>Office hours</Label>
								<Input v-model="form.office_hours" :disabled="!canEdit" />
							</div>
						</div>
					</div>
				</section>

				<!-- Carrier tracking -->
				<section v-else-if="section === 'tracking'" class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
					<h2 class="label-caps mb-4">Carrier auto-tracking</h2>
					<div class="grid gap-4 sm:grid-cols-2">
						<div class="space-y-1.5">
							<Label>Provider</Label>
							<Select
								v-model="form.tracking_provider"
								:options="[{ value: '', label: 'None (manual milestones)' }, 'ShipsGo', 'Terminal49']"
								:disabled="!canEdit"
							/>
						</div>
						<div class="space-y-1.5">
							<Label>API key {{ form.tracking_api_key_set ? "(set — enter to replace)" : "" }}</Label>
							<Input v-model="form.tracking_api_key" type="password" :disabled="!canEdit" placeholder="••••••••" />
						</div>
					</div>
					<p class="mt-3 text-xs text-muted-foreground">
						With a provider configured, active containers sync hourly and a
						<b>Sync tracking</b> button appears on each container.
					</p>
					<div class="mt-4 rounded-xl bg-gray-50 p-4">
						<div class="flex items-center justify-between gap-2">
							<Label>Inbound webhook (push updates)</Label>
							<button type="button" class="inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline" @click="copyWebhook">
								<Copy class="h-3.5 w-3.5" /> Copy URL
							</button>
						</div>
						<code class="mt-2 block overflow-x-auto whitespace-nowrap rounded-lg bg-white px-3 py-2 text-[11px] text-gray-600 ring-1 ring-gray-200">
							POST {{ webhookUrl() }}
						</code>
						<p class="mt-2 text-xs text-muted-foreground">
							Body: <code>{"container_no", "event", "datetime?", "location?", "eta?"}</code> — point any provider's webhook here.
						</p>
					</div>
				</section>

				<!-- Notifications -->
				<section v-else-if="section === 'notifications'" class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
					<h2 class="label-caps mb-4">Customer notifications</h2>
					<div class="mb-4 flex flex-wrap gap-2">
						<label
							v-for="ch in [
								{ field: 'email_enabled', label: 'Email' },
								{ field: 'sms_enabled', label: 'SMS' },
								{ field: 'whatsapp_enabled', label: 'WhatsApp' },
							]"
							:key="ch.field"
							class="flex cursor-pointer items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors"
							:class="form[ch.field] ? 'border-brand-400 bg-brand-50 text-brand-800' : 'border-gray-200 text-gray-600'"
						>
							<input
								type="checkbox"
								class="h-4 w-4 rounded accent-[#b8860b]"
								:checked="!!form[ch.field]"
								:disabled="!canEdit"
								@change="form[ch.field] = form[ch.field] ? 0 : 1"
							/>
							{{ ch.label }}
						</label>
					</div>
					<div class="grid gap-4">
						<div class="space-y-1.5">
							<Label>Email subject</Label>
							<Input v-model="form.email_subject_template" :disabled="!canEdit" />
						</div>
						<div class="space-y-1.5">
							<Label>Email body</Label>
							<Textarea v-model="form.email_body_template" :rows="5" :disabled="!canEdit" />
						</div>
						<div class="space-y-1.5">
							<Label>SMS / WhatsApp message</Label>
							<Textarea v-model="form.sms_template" :rows="2" :disabled="!canEdit" />
							<p class="text-xs text-muted-foreground">
								Variables: <code>{customer_name} {tracking_no} {milestone} {location} {business_name} {tracking_link}</code>
							</p>
						</div>
					</div>
					<div class="mt-4 grid gap-4 sm:grid-cols-2">
						<div class="space-y-1.5">
							<Label>WhatsApp gateway URL</Label>
							<Input v-model="form.whatsapp_gateway_url" :disabled="!canEdit" placeholder="https://gateway.example.com/send" />
							<p class="text-xs text-muted-foreground">Receives JSON <code>{"to", "message"}</code>.</p>
						</div>
						<div class="space-y-1.5">
							<Label>Gateway token {{ form.whatsapp_api_token_set ? "(set — enter to replace)" : "" }}</Label>
							<Input v-model="form.whatsapp_api_token" type="password" :disabled="!canEdit" placeholder="••••••••" />
						</div>
					</div>
				</section>

				<!-- Branches -->
				<section v-else-if="section === 'branches'" class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
					<h2 class="label-caps mb-4">Branches</h2>
					<p class="mb-4 text-sm text-muted-foreground">
						Branches let you file shipments and deliveries per location and filter
						reports by branch.
					</p>
					<div v-if="canEdit" class="mb-5 flex gap-2">
						<Input v-model="branchName" placeholder="e.g. Tema Yard" class="max-w-xs" @keyup.enter="addBranch" />
						<Button :loading="branchSaving" @click="addBranch"><Plus class="h-4 w-4" /> Add branch</Button>
					</div>
					<div v-if="!branches.length" class="rounded-xl bg-gray-50 px-4 py-8 text-center text-sm text-muted-foreground">
						No branches yet — everything files under head office.
					</div>
					<div v-else class="flex flex-wrap gap-2">
						<span
							v-for="b in branches"
							:key="b"
							class="inline-flex items-center gap-2 rounded-xl border border-gray-150 px-3.5 py-2.5 text-sm font-medium"
						>
							<GitBranch class="h-4 w-4 text-brand-700" /> {{ b }}
						</span>
					</div>
				</section>

				<!-- Staff & Roles -->
				<section v-else-if="section === 'staff' && canEdit" class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
					<div class="mb-4 flex flex-wrap items-center gap-2">
						<h2 class="label-caps min-w-0 flex-1">Staff & roles</h2>
						<Button size="sm" variant="outline" @click="openRole()"><ShieldCheck class="h-4 w-4" /> New role</Button>
						<Button size="sm" @click="staffOpen = true"><UserPlus class="h-4 w-4" /> Add staff</Button>
					</div>

					<!-- Roles -->
					<div class="mb-5 flex flex-wrap gap-2">
						<div
							v-for="r in roles"
							:key="r.name"
							class="group flex items-center gap-2.5 rounded-xl border border-gray-150 px-3.5 py-2.5"
						>
							<span class="text-sm font-medium">{{ r.role_name }}</span>
							<span class="rounded-full bg-gray-100 px-2 py-0.5 text-[10.5px] font-semibold text-gray-500">
								{{ r.is_admin ? "ADMIN" : r.all_pages ? "ALL PAGES" : `${r.pages.length} pages` }}
							</span>
							<span class="text-xs text-muted-foreground tabular-nums">{{ r.members }} member(s)</span>
							<button type="button" class="text-xs font-medium text-brand-700 opacity-0 transition-opacity hover:underline group-hover:opacity-100" @click="openRole(r)">Edit</button>
							<button
								v-if="!r.members"
								type="button"
								class="text-gray-300 opacity-0 transition-opacity hover:text-red-600 group-hover:opacity-100"
								@click="deleteRole(r)"
							>
								<Trash2 class="h-3.5 w-3.5" />
							</button>
						</div>
					</div>

					<!-- Staff list -->
					<div class="overflow-x-auto">
						<table class="w-full min-w-[560px] text-sm">
							<thead>
								<tr class="text-left">
									<th class="label-caps pb-2 pr-4">Staff</th>
									<th class="label-caps pb-2 pr-4">Email</th>
									<th class="label-caps pb-2">Role</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="u in staff" :key="u.name" class="border-t border-gray-100">
									<td class="py-2.5 pr-4 font-medium">
										{{ u.full_name || u.name }}
										<span v-if="u.is_super" class="ml-1 rounded-full bg-brand-600/10 px-2 py-0.5 text-[10px] font-bold text-brand-700">MANAGER</span>
										<span v-else-if="u.is_driver" class="ml-1 rounded-full bg-cyan-50 px-2 py-0.5 text-[10px] font-bold text-cyan-700">DRIVER</span>
									</td>
									<td class="py-2.5 pr-4 text-muted-foreground">{{ u.name }}</td>
									<td class="py-2.5">
										<span v-if="u.is_super || u.is_driver" class="text-xs text-muted-foreground">
											{{ u.is_super ? "Full access" : "Dispatch (own runs)" }}
										</span>
										<Select
											v-else
											:model-value="u.bwm_logistics_role || ''"
											:options="[{ value: '', label: 'Default (by base role)' }, ...roles.map((r) => ({ value: r.name, label: r.role_name }))]"
											class="max-w-52"
											@update:model-value="(v) => changeRole(u, v)"
										/>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</section>
			</div>
		</div>

		<!-- ── Add staff dialog ─────────────────────────────────────────── -->
		<Dialog v-model:open="staffOpen" title="Add staff member">
			<div class="space-y-4">
				<div class="space-y-1.5">
					<Label required>Full name</Label>
					<Input v-model="staffForm.full_name" placeholder="e.g. Efua Mensah" />
				</div>
				<div class="space-y-1.5">
					<Label required>Email</Label>
					<Input v-model="staffForm.email" type="email" placeholder="staff@example.com" />
					<p class="text-xs text-muted-foreground">They'll receive an email with a link to set their own password.</p>
				</div>
				<div class="space-y-1.5">
					<Label>Role</Label>
					<Select
						v-model="staffForm.logistics_role"
						:options="[{ value: '', label: 'Default (Operations)' }, ...roles.map((r) => ({ value: r.name, label: r.role_name }))]"
					/>
				</div>
			</div>
			<template #footer>
				<div class="flex justify-end gap-2">
					<Button variant="outline" @click="staffOpen = false">Cancel</Button>
					<Button :loading="staffSaving" @click="createStaff">Create & invite</Button>
				</div>
			</template>
		</Dialog>

		<!-- ── Role editor dialog ───────────────────────────────────────── -->
		<Dialog v-model:open="roleOpen" :title="roleForm.name ? 'Edit role' : 'New role'" size="wide">
			<div class="space-y-4">
				<div class="space-y-1.5">
					<Label required>Role name</Label>
					<Input v-model="roleForm.role_name" placeholder="e.g. Front Desk" />
				</div>
				<div class="flex flex-wrap gap-2">
					<label
						class="flex cursor-pointer items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium"
						:class="roleForm.is_admin ? 'border-brand-400 bg-brand-50 text-brand-800' : 'border-gray-200 text-gray-600'"
					>
						<input type="checkbox" class="h-4 w-4 rounded accent-[#b8860b]" :checked="!!roleForm.is_admin" @change="roleForm.is_admin = roleForm.is_admin ? 0 : 1" />
						Administrator (everything + Settings)
					</label>
					<label
						class="flex cursor-pointer items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium"
						:class="roleForm.all_pages ? 'border-brand-400 bg-brand-50 text-brand-800' : 'border-gray-200 text-gray-600'"
					>
						<input type="checkbox" class="h-4 w-4 rounded accent-[#b8860b]" :checked="!!roleForm.all_pages" :disabled="!!roleForm.is_admin" @change="roleForm.all_pages = roleForm.all_pages ? 0 : 1" />
						All pages (except Settings)
					</label>
				</div>
				<div v-if="!roleForm.is_admin && !roleForm.all_pages" class="space-y-1.5">
					<Label>Pages this role can see</Label>
					<div class="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
						<label
							v-for="p in pageCatalog"
							:key="p.key"
							class="flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm"
							:class="roleForm.pages.has(p.key) ? 'border-brand-400 bg-brand-50' : 'border-gray-150 hover:bg-gray-50'"
						>
							<input type="checkbox" class="h-4 w-4 rounded accent-[#b8860b]" :checked="roleForm.pages.has(p.key)" @change="togglePage(p.key)" />
							{{ p.label }}
						</label>
					</div>
					<p class="text-xs text-muted-foreground">
						Billing or Reports also unlocks the payment-recording APIs for this role.
					</p>
				</div>
			</div>
			<template #footer>
				<div class="flex justify-end gap-2">
					<Button variant="outline" @click="roleOpen = false">Cancel</Button>
					<Button :loading="roleSaving" @click="saveRole">Save role</Button>
				</div>
			</template>
		</Dialog>
	</div>
</template>
