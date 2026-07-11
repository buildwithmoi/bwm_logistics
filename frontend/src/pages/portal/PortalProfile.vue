<script setup lang="ts">
import { onMounted, ref } from "vue";
import { UserRound, Mail, MessageSquareText } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { useToast } from "@/composables/useToast";

const toast = useToast();

interface Profile {
	customer_name: string;
	email_id?: string;
	mobile_no?: string;
	bwm_notify_email?: number;
	bwm_notify_sms?: number;
	bwm_notify_whatsapp?: number;
	whatsapp_available?: boolean;
	user: string;
}
const profile = ref<Profile | null>(null);
const loading = ref(true);

onMounted(async () => {
	try {
		profile.value = await call<Profile>("bwm_logistics.api.portal.get_profile");
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load your profile");
	} finally {
		loading.value = false;
	}
});

async function toggle(field: "bwm_notify_email" | "bwm_notify_sms" | "bwm_notify_whatsapp") {
	if (!profile.value) return;
	const next = profile.value[field] ? 0 : 1;
	profile.value[field] = next;
	try {
		await call("bwm_logistics.api.portal.update_prefs", {
			notify_email: profile.value.bwm_notify_email ?? 1,
			notify_sms: profile.value.bwm_notify_sms ?? 1,
			notify_whatsapp: profile.value.bwm_notify_whatsapp ?? 1,
		});
		toast.success("Preferences saved");
	} catch (e: unknown) {
		profile.value[field] = next ? 0 : 1; // revert
		toast.error((e as { message?: string })?.message || "Could not save preferences");
	}
}
</script>

<template>
	<div class="mx-auto max-w-2xl">
		<header class="mb-5">
			<h1 class="text-2xl font-semibold tracking-tight">Profile</h1>
		</header>

		<div v-if="loading" class="py-16 text-center text-sm text-muted-foreground">Loading…</div>
		<template v-else-if="profile">
			<!-- Identity -->
			<div class="flex items-center gap-4 rounded-3xl bg-white p-6 ring-1 ring-gray-100">
				<span class="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-400 to-brand-600 text-xl font-bold text-coal-900">
					{{ profile.customer_name?.[0]?.toUpperCase() || "C" }}
				</span>
				<div class="min-w-0">
					<div class="text-lg font-semibold">{{ profile.customer_name }}</div>
					<div class="text-sm text-muted-foreground">{{ profile.user }}</div>
					<div v-if="profile.mobile_no" class="text-sm text-muted-foreground">{{ profile.mobile_no }}</div>
				</div>
			</div>

			<!-- Notification prefs -->
			<div class="mt-4 rounded-3xl bg-white p-6 ring-1 ring-gray-100">
				<h2 class="label-caps mb-4">How should we update you?</h2>
				<div class="space-y-3">
					<label class="flex cursor-pointer items-center gap-3 rounded-xl border border-gray-100 px-4 py-3.5 transition-colors hover:bg-gray-50">
						<span class="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600/10 text-brand-700">
							<Mail class="h-4 w-4" />
						</span>
						<span class="min-w-0 flex-1">
							<span class="block text-sm font-medium">Email updates</span>
							<span class="block text-xs text-muted-foreground">Milestone updates to {{ profile.email_id || "your email" }}</span>
						</span>
						<input
							type="checkbox"
							class="h-4 w-4 rounded accent-[#b8860b]"
							:checked="!!profile.bwm_notify_email"
							@change="toggle('bwm_notify_email')"
						/>
					</label>
					<label class="flex cursor-pointer items-center gap-3 rounded-xl border border-gray-100 px-4 py-3.5 transition-colors hover:bg-gray-50">
						<span class="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600/10 text-brand-700">
							<MessageSquareText class="h-4 w-4" />
						</span>
						<span class="min-w-0 flex-1">
							<span class="block text-sm font-medium">SMS updates</span>
							<span class="block text-xs text-muted-foreground">Text messages to {{ profile.mobile_no || "your phone" }}</span>
						</span>
						<input
							type="checkbox"
							class="h-4 w-4 rounded accent-[#b8860b]"
							:checked="!!profile.bwm_notify_sms"
							@change="toggle('bwm_notify_sms')"
						/>
					</label>
					<label
						v-if="profile.whatsapp_available"
						class="flex cursor-pointer items-center gap-3 rounded-xl border border-gray-100 px-4 py-3.5 transition-colors hover:bg-gray-50"
					>
						<span class="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-600/10 text-emerald-700">
							<MessageSquareText class="h-4 w-4" />
						</span>
						<span class="min-w-0 flex-1">
							<span class="block text-sm font-medium">WhatsApp updates</span>
							<span class="block text-xs text-muted-foreground">Messages to {{ profile.mobile_no || "your phone" }}</span>
						</span>
						<input
							type="checkbox"
							class="h-4 w-4 rounded accent-[#b8860b]"
							:checked="!!profile.bwm_notify_whatsapp"
							@change="toggle('bwm_notify_whatsapp')"
						/>
					</label>
				</div>
			</div>

			<!-- Password note -->
			<div class="mt-4 flex items-start gap-3 rounded-2xl bg-gray-50 p-5 text-sm text-muted-foreground">
				<UserRound class="mt-0.5 h-4 w-4 shrink-0" />
				<p>
					To change your password, use "Forgot?" on the login screen — we'll email you
					a secure reset link. For anything else, contact our team.
				</p>
			</div>
		</template>
	</div>
</template>
