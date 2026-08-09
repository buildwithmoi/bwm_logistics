<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { Plus } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Select from "@/components/ui/Select.vue";
import Sheet from "@/components/ui/Sheet.vue";
import Badge from "@/components/ui/Badge.vue";
import PageHeader from "@/components/ui/PageHeader.vue";
import DataTable from "@/components/ui/DataTable.vue";
import ListToolbar from "@/components/ui/ListToolbar.vue";

// The goods catalogue — "what do we ship?"
//
// Container contents used to be typed by hand, so "US Hen Leg Quarter" and
// "Hen Leg Quarter" were two products and no balance could be trusted. This is
// the list those lines now pick from; Trade direction decides which container
// is offered which goods.
const toast = useToast();
const session = useSessionStore();

interface Row extends Record<string, unknown> {
	name: string;
	item_name: string;
	stock_uom: string;
	bwm_trade_direction?: string;
}
const rows = ref<Row[]>([]);
const loading = ref(false);
const search = ref("");
const directionFilter = ref("");
const canWrite = computed(() => session.can("settings", "create") || session.can("containers", "create"));

async function load() {
	loading.value = true;
	try {
		rows.value = await call<Row[]>("bwm_logistics.api.items.list_items", {
			search: search.value || null,
			direction: directionFilter.value || null,
			limit: 200,
		});
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load items");
	} finally {
		loading.value = false;
	}
}
let timer: ReturnType<typeof setTimeout>;
watch(search, () => {
	clearTimeout(timer);
	timer = setTimeout(load, 300);
});
watch(directionFilter, load);
onMounted(load);

const columns = [
	{ key: "item_name", label: "Item", primary: true },
	{ key: "bwm_trade_direction", label: "Direction", trailing: true },
	{ key: "stock_uom", label: "Unit" },
];

// ── create / edit ───────────────────────────────────────────────────────────
const open = ref(false);
const saving = ref(false);
const units = ref<string[]>(["Nos"]);
const form = ref<{ name?: string; item_name: string; unit: string; direction: string }>({
	item_name: "",
	unit: "Nos",
	direction: "Both",
});

function openNew() {
	form.value = { item_name: "", unit: units.value[0] || "Nos", direction: "Both" };
	open.value = true;
}
function openEdit(row: Row) {
	if (!canWrite.value) return;
	form.value = {
		name: row.name,
		item_name: row.item_name,
		unit: row.stock_uom || "Nos",
		direction: row.bwm_trade_direction || "Both",
	};
	open.value = true;
}

async function save() {
	if (!form.value.item_name.trim()) {
		toast.warning("Give the item a name");
		return;
	}
	saving.value = true;
	try {
		await call("bwm_logistics.api.items.save_item", { payload: { ...form.value } });
		toast.success(form.value.name ? "Item updated" : "Item added");
		open.value = false;
		await load();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not save item");
	} finally {
		saving.value = false;
	}
}

onMounted(async () => {
	try {
		units.value = await call<string[]>("bwm_logistics.api.items.units");
	} catch {
		/* fall back to the default */
	}
});
</script>

<template>
	<div class="mx-auto max-w-4xl">
		<PageHeader
			title="Items"
			subtitle="The goods you ship. Container contents pick from this list, so a name is only spelled once."
		>
			<template v-if="canWrite" #actions>
				<Button @click="openNew"><Plus class="h-4 w-4" aria-hidden="true" /> New item</Button>
			</template>
		</PageHeader>

		<ListToolbar
			v-model:search="search"
			v-model:lens="directionFilter"
			search-label="Search items"
			search-placeholder="Search goods…"
			lens-label="Trade direction"
			:lens-options="[
				{ value: '', label: 'All directions' },
				{ value: 'Import', label: 'Import goods' },
				{ value: 'Export', label: 'Export goods' },
			]"
		/>

		<DataTable
			:columns="columns"
			:rows="rows"
			:loading="loading"
			:clickable="canWrite"
			empty-text="No items yet — add the goods you ship."
			@row-click="(r) => openEdit(r as Row)"
		>
			<template #cell-item_name="{ row }">
				<span class="font-medium">{{ row.item_name }}</span>
			</template>
			<template #cell-bwm_trade_direction="{ value }">
				<Badge :tone="value === 'Import' ? 'info' : value === 'Export' ? 'violet' : 'neutral'">
					{{ value || "Both" }}
				</Badge>
			</template>
		</DataTable>

		<Sheet v-model:open="open" :title="form.name ? 'Edit item' : 'New item'">
			<div class="space-y-4">
				<div class="space-y-1.5">
					<Label for="it-name" required>Name</Label>
					<Input id="it-name" v-model="form.item_name" placeholder="e.g. Frozen Chicken Back" />
				</div>
				<div class="space-y-1.5">
					<Label for="it-unit">Unit</Label>
					<Select id="it-unit" v-model="form.unit" :options="units" />
				</div>
				<div class="space-y-1.5">
					<Label for="it-dir">Trade direction</Label>
					<Select id="it-dir" v-model="form.direction" :options="['Both', 'Import', 'Export']" />
					<p class="text-xs text-muted-foreground">
						Which container direction may carry this item. “Both” shows everywhere.
					</p>
				</div>
			</div>
			<template #footer>
				<div class="flex justify-end gap-2">
					<Button variant="outline" @click="open = false">Cancel</Button>
					<Button :loading="saving" @click="save">{{ form.name ? "Save item" : "Add item" }}</Button>
				</div>
			</template>
		</Sheet>
	</div>
</template>
