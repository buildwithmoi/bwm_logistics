<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { Truck, Plus } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtDate } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Select from "@/components/ui/Select.vue";
import Textarea from "@/components/ui/Textarea.vue";
import Dialog from "@/components/ui/Dialog.vue";
import StatusBadge from "@/components/StatusBadge.vue";

const toast = useToast();

interface Pickup {
	name: string;
	status: string;
	pickup_address: string;
	preferred_date?: string;
	time_window?: string;
	shipment?: string;
	creation: string;
}
const pickups = ref<Pickup[]>([]);
const loading = ref(true);

async function load() {
	loading.value = true;
	try {
		pickups.value = await call<Pickup[]>("bwm_logistics.api.portal.my_pickups");
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load pickups");
	} finally {
		loading.value = false;
	}
}
onMounted(load);

const dialogOpen = ref(false);
const saving = ref(false);
const form = reactive({
	pickup_address: "",
	contact_phone: "",
	preferred_date: "",
	time_window: "Any time",
	notes: "",
});

async function save() {
	if (!form.pickup_address.trim()) {
		toast.warning("Tell us where to pick up from");
		return;
	}
	saving.value = true;
	try {
		await call("bwm_logistics.api.portal.request_pickup", { payload: { ...form } });
		toast.success("Pickup requested — we'll schedule it and keep you posted");
		dialogOpen.value = false;
		form.pickup_address = "";
		form.notes = "";
		await load();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not request pickup");
	} finally {
		saving.value = false;
	}
}
</script>

<template>
	<div class="mx-auto max-w-3xl">
		<header class="mb-5 flex flex-wrap items-center gap-3">
			<div class="min-w-0 flex-1">
				<h1 class="text-2xl font-semibold tracking-tight">Pickups</h1>
				<p class="mt-1 text-sm text-muted-foreground">Book a pickup and we'll come to you.</p>
			</div>
			<Button @click="dialogOpen = true"><Plus class="h-4 w-4" /> Request pickup</Button>
		</header>

		<div v-if="loading" class="py-16 text-center text-sm text-muted-foreground">Loading…</div>
		<div
			v-else-if="!pickups.length"
			class="flex flex-col items-center rounded-3xl bg-white p-14 text-center ring-1 ring-gray-100"
		>
			<span class="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-600/10 text-brand-700">
				<Truck class="h-6 w-6" />
			</span>
			<p class="text-sm text-muted-foreground">No pickups yet — request one and we'll schedule it.</p>
		</div>
		<div v-else class="space-y-3">
			<div
				v-for="p in pickups"
				:key="p.name"
				class="flex flex-wrap items-center gap-4 rounded-2xl bg-white p-5 ring-1 ring-gray-100"
			>
				<span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-600/10 text-brand-700">
					<Truck class="h-5 w-5" />
				</span>
				<div class="min-w-0 flex-1">
					<div class="flex flex-wrap items-center gap-2">
						<span class="font-semibold">{{ p.name }}</span>
						<StatusBadge :status="p.status" />
					</div>
					<div class="mt-0.5 text-sm text-muted-foreground">{{ p.pickup_address }}</div>
					<div class="text-xs text-muted-foreground">
						{{ fmtDate(p.preferred_date) }} · {{ p.time_window }}
						<RouterLink
							v-if="p.shipment"
							:to="`/portal/shipments/${p.shipment}`"
							class="ml-1 font-medium text-brand-700 hover:underline"
						>→ {{ p.shipment }}</RouterLink>
					</div>
				</div>
			</div>
		</div>

		<!-- Request dialog -->
		<Dialog v-model:open="dialogOpen" title="Request a pickup">
			<div class="space-y-4">
				<div class="space-y-1.5">
					<Label required>Pickup address</Label>
					<Textarea v-model="form.pickup_address" :rows="2" placeholder="Street, area, landmarks…" />
				</div>
				<div class="space-y-1.5">
					<Label>Contact phone</Label>
					<Input v-model="form.contact_phone" placeholder="+233…" />
				</div>
				<div class="grid grid-cols-2 gap-3">
					<div class="space-y-1.5">
						<Label>Preferred date</Label>
						<Input v-model="form.preferred_date" type="date" />
					</div>
					<div class="space-y-1.5">
						<Label>Time</Label>
						<Select v-model="form.time_window" :options="['Any time', 'Morning', 'Afternoon', 'Evening']" />
					</div>
				</div>
				<div class="space-y-1.5">
					<Label>Notes</Label>
					<Textarea v-model="form.notes" :rows="2" placeholder="What are we picking up?" />
				</div>
			</div>
			<template #footer>
				<div class="flex justify-end gap-2">
					<Button variant="outline" @click="dialogOpen = false">Cancel</Button>
					<Button :loading="saving" @click="save">Request pickup</Button>
				</div>
			</template>
		</Dialog>
	</div>
</template>
