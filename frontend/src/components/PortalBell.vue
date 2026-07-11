<script setup lang="ts">
import { ref } from "vue";
import { RouterLink } from "vue-router";
import { onClickOutside } from "@vueuse/core";
import { Bell, Mail, MessageSquareText } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtDateTime } from "@/lib/format";

// In-portal notification feed (FR-POR-6) — the customer's own send log,
// straight from Notification Log Entry. No unread bookkeeping at this stage;
// it's a simple "what have you told me" feed.
interface Item {
	name: string;
	creation: string;
	channel: string;
	milestone?: string;
	shipment?: string;
	subject?: string;
	message?: string;
}
const open = ref(false);
const items = ref<Item[]>([]);
const loaded = ref(false);
const rootRef = ref<HTMLElement | null>(null);
onClickOutside(rootRef, () => (open.value = false));

async function toggle() {
	open.value = !open.value;
	if (open.value && !loaded.value) {
		try {
			items.value = await call<Item[]>("bwm_logistics.api.portal.my_notifications");
		} catch {
			/* feed degrades to empty */
		} finally {
			loaded.value = true;
		}
	}
}
</script>

<template>
	<div ref="rootRef" class="relative">
		<button
			type="button"
			class="flex h-9 w-9 items-center justify-center rounded-lg transition-colors hover:bg-white/[0.08]"
			:class="open ? 'bg-white/[0.14] text-white' : 'text-white/65 hover:text-white'"
			title="Notifications"
			@click="toggle"
		>
			<Bell class="h-4 w-4" />
		</button>

		<transition
			enter-active-class="transition duration-100 ease-out"
			enter-from-class="opacity-0 -translate-y-1"
			enter-to-class="opacity-100 translate-y-0"
			leave-active-class="transition duration-75 ease-in"
			leave-from-class="opacity-100"
			leave-to-class="opacity-0"
		>
			<div
				v-if="open"
				class="absolute right-0 top-full z-50 mt-1.5 w-80 overflow-hidden rounded-xl border border-black/5 bg-white text-gray-900 shadow-pop"
			>
				<div class="border-b border-gray-100 px-4 py-3 text-sm font-semibold">Notifications</div>
				<div class="max-h-80 overflow-y-auto">
					<div v-if="!loaded" class="px-4 py-8 text-center text-sm text-muted-foreground">Loading…</div>
					<div v-else-if="!items.length" class="px-4 py-8 text-center text-sm text-muted-foreground">
						Nothing yet — updates about your shipments land here.
					</div>
					<RouterLink
						v-for="n in items"
						:key="n.name"
						:to="n.shipment ? `/portal/shipments/${n.shipment}` : '/portal'"
						class="flex gap-3 border-b border-gray-50 px-4 py-3 transition-colors last:border-0 hover:bg-gray-50"
						@click="open = false"
					>
						<span class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-brand-600/10 text-brand-700">
							<Mail v-if="n.channel === 'Email'" class="h-3.5 w-3.5" />
							<MessageSquareText v-else class="h-3.5 w-3.5" />
						</span>
						<span class="min-w-0 flex-1">
							<span class="block truncate text-[13px] font-medium">
								{{ n.milestone || n.subject || "Update" }}
								<template v-if="n.shipment"> · {{ n.shipment }}</template>
							</span>
							<span class="block text-[11px] tabular-nums text-muted-foreground">{{ fmtDateTime(n.creation) }}</span>
						</span>
					</RouterLink>
				</div>
			</div>
		</transition>
	</div>
</template>
