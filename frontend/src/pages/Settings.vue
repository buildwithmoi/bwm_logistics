<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { Save, Copy } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Select from "@/components/ui/Select.vue";
import Textarea from "@/components/ui/Textarea.vue";

const toast = useToast();
const session = useSessionStore();
const canEdit = session.hasRole("Logistics Manager", "System Manager", "Administrator");

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
});

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
	<div class="mx-auto max-w-3xl">
		<header class="mb-5 flex flex-wrap items-center gap-3">
			<div class="min-w-0 flex-1">
				<h1 class="text-2xl font-semibold tracking-tight">Settings</h1>
				<p class="mt-1 text-sm text-muted-foreground">Branding, tracking, notifications, and your public website.</p>
			</div>
			<Button v-if="canEdit" :loading="saving" @click="save"><Save class="h-4 w-4" /> Save</Button>
		</header>

		<div v-if="loading" class="py-16 text-center text-sm text-muted-foreground">Loading…</div>
		<div v-else class="space-y-4">
			<!-- Branding -->
			<section class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
				<h2 class="label-caps mb-4">Branding</h2>
				<div class="grid gap-4 sm:grid-cols-2">
					<div class="space-y-1.5">
						<Label>Business name</Label>
						<Input v-model="form.business_name" :disabled="!canEdit" placeholder="BWM Logistics" />
					</div>
					<div class="space-y-1.5">
						<Label>Tracking number prefix</Label>
						<Input v-model="form.tracking_prefix" :disabled="!canEdit" placeholder="BWM" />
						<p class="text-xs text-muted-foreground">New shipments become PREFIX-000001. Existing numbers keep their prefix.</p>
					</div>
				</div>
			</section>

			<!-- Carrier tracking -->
			<section class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
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
			<section class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
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

			<!-- Website -->
			<section class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
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
		</div>
	</div>
</template>
