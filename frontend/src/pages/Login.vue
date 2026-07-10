<script setup lang="ts">
import { computed, ref } from "vue";
import {
	Eye,
	EyeOff,
	Ship,
	Container,
	Truck,
	AtSign,
	Lock,
	ArrowRight,
	ShieldCheck,
	LayoutDashboard,
	Wrench,
} from "lucide-vue-next";
import { login, fetchDestinations, type LoginDestinations } from "@/lib/auth";
import { useToast } from "@/composables/useToast";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import BrandLogo from "@/components/BrandLogo.vue";

const toast = useToast();

// Frappe's /api/method/login accepts either email or username in `usr`,
// so the field is plain text and the placeholder is intentionally generic.
const identifier = ref("");
const password = ref("");
const showPassword = ref(false);
const busy = ref(false);

// Two phases: the sign-in form, then (for users with more than one home) an
// Operator/Desk chooser. Single-home users skip straight to their destination.
const phase = ref<"form" | "choose">("form");
const dest = ref<LoginDestinations | null>(null);
const backUrl = ref("/home");
const firstName = computed(() => (dest.value?.full_name || "").split(/\s+/)[0] || "");

function safeBack(): string {
	const t = new URLSearchParams(window.location.search).get("redirect-to");
	return t && t.startsWith("/") && !t.startsWith("//") ? t : "/home";
}

// Full page navigations (not router.push) so www/logistics.html re-renders
// with a fresh CSRF token + bootinfo for the new session.
function goOperator() { window.location.href = "/logistics"; }
function goPortal() { window.location.href = "/logistics/portal"; }
function goDesk() { window.location.href = "/app"; }
function goBack() { window.location.href = backUrl.value || "/home"; }

async function submit() {
	if (!identifier.value || !password.value) {
		toast.warning("Please fill in both fields");
		return;
	}
	busy.value = true;
	try {
		await login(identifier.value.trim(), password.value);
		toast.success("Welcome back");
		backUrl.value = safeBack();
		let d: LoginDestinations | null = null;
		try { d = await fetchDestinations(); } catch { /* fall through */ }

		if (d && d.has_operator && d.has_desk) {
			// More than one home → let them choose.
			dest.value = d;
			phase.value = "choose";
		} else if (d && d.has_operator) {
			goOperator();
		} else if (d && d.has_customer) {
			goPortal();
		} else if (d && d.has_desk) {
			goDesk();
		} else {
			// No app access (e.g. an unlinked website user) → back to the site.
			goBack();
		}
	} catch (err: unknown) {
		toast.error((err as { message?: string })?.message || "Could not sign in");
	} finally {
		busy.value = false;
	}
}
</script>

<template>
	<div class="relative flex min-h-screen overflow-hidden bg-white">
		<!-- Brand panel right edge — wave silhouette via clip-path (see
		     ex_beauty; tangent-continuous cubics so there are no cusps). -->
		<svg width="0" height="0" class="pointer-events-none absolute" aria-hidden="true">
			<defs>
				<clipPath id="bwmBrandCurve" clipPathUnits="objectBoundingBox">
					<path
						d="M 0,0
						   L 0.85,0
						   C 1.0,0 1.0,0.2 0.85,0.2
						   C 0.70,0.2 0.70,0.4 0.85,0.4
						   C 1.0,0.4 1.0,0.6 0.85,0.6
						   C 0.70,0.6 0.70,0.8 0.85,0.8
						   C 1.0,0.8 1.0,1 0.85,1
						   L 0,1 Z"
					/>
				</clipPath>
			</defs>
		</svg>

		<!-- ── Brand panel (lg+) ──────────────────────────────────────────── -->
		<aside
			class="bwm-brand-panel relative hidden flex-col justify-between overflow-hidden p-12 text-white lg:flex lg:w-[60%] xl:w-[62%]"
		>
			<!-- Black ground with a gold glow — the gold/black/white identity. -->
			<div class="absolute inset-0 bg-coal-900"></div>
			<div class="pointer-events-none absolute inset-0">
				<div class="bwm-blob bwm-blob-a"></div>
				<div class="bwm-blob bwm-blob-b"></div>
				<div class="bwm-blob bwm-blob-c"></div>
				<div class="bwm-sparkle" style="top:18%;left:22%;animation-delay:.0s"></div>
				<div class="bwm-sparkle" style="top:35%;left:78%;animation-delay:.7s"></div>
				<div class="bwm-sparkle" style="top:62%;left:30%;animation-delay:1.3s"></div>
				<div class="bwm-sparkle" style="top:80%;left:68%;animation-delay:1.9s"></div>
				<div class="bwm-sparkle" style="top:8%;left:55%;animation-delay:2.4s"></div>
			</div>

			<!-- Brand mark -->
			<div class="relative z-10 flex items-center gap-3">
				<div
					class="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-400 to-brand-600 text-coal-900 ring-1 ring-white/20"
				>
					<BrandLogo :size="28" />
				</div>
				<div>
					<div class="text-lg font-bold tracking-tight">BWM Logistics</div>
					<div class="text-xs text-white/60">Port to doorstep, tracked.</div>
				</div>
			</div>

			<!-- Hero copy -->
			<div class="relative z-10 max-w-md">
				<h2 class="text-4xl font-bold leading-tight tracking-tight xl:text-5xl">
					Every container. Every customer.
					<span class="text-brand-400">Every milestone.</span>
				</h2>
				<p class="mt-4 text-base text-white/70 xl:text-lg">
					Containers, shipments, deliveries, and payments — one calm
					dashboard for your whole operation, and a portal your
					customers will love.
				</p>

				<div class="mt-8 flex flex-wrap gap-2">
					<div class="bwm-chip"><Ship class="h-3.5 w-3.5" /> Import &amp; Export</div>
					<div class="bwm-chip"><Container class="h-3.5 w-3.5" /> Consolidation</div>
					<div class="bwm-chip"><Truck class="h-3.5 w-3.5" /> Delivery</div>
				</div>
			</div>

			<div class="relative z-10 text-xs text-white/50">
				© 2026 Build With Moi
			</div>
		</aside>

		<!-- ── Form column ────────────────────────────────────────────────── -->
		<section class="relative z-10 flex w-full flex-col items-center justify-center px-6 py-12 lg:w-[40%] xl:w-[38%]">
			<!-- Mobile brand mark -->
			<div class="mb-8 flex flex-col items-center lg:hidden">
				<div
					class="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-400 to-brand-600 text-coal-900 shadow-lg shadow-brand-200"
				>
					<BrandLogo :size="34" />
				</div>
				<div class="text-lg font-bold">BWM Logistics</div>
			</div>

			<div class="w-full max-w-sm bwm-form-enter">
				<!-- Phase 1 — sign-in form -->
				<div v-if="phase === 'form'" class="rounded-3xl border border-gray-100 bg-white/95 p-8 shadow-[0_28px_70px_-32px_rgba(184,134,11,0.35)] backdrop-blur-sm">
					<div class="mb-6 space-y-2">
						<span class="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-700">
							<span class="h-px w-5 bg-brand-300"></span> Logistics Portal
						</span>
						<h1 class="text-[27px] font-bold leading-tight tracking-tight text-gray-900">Welcome back</h1>
						<p class="text-sm text-gray-500">Sign in to track, manage, and pay.</p>
					</div>

					<form class="space-y-5" @submit.prevent="submit">
						<div class="space-y-1.5">
							<Label for="identifier" required>Username or email</Label>
							<div class="relative">
								<AtSign class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
								<Input
									id="identifier"
									v-model="identifier"
									type="text"
									autocomplete="username"
									placeholder="Your login"
									:disabled="busy"
									class="h-11 pl-10"
								/>
							</div>
						</div>

						<div class="space-y-1.5">
							<div class="flex items-center justify-between">
								<Label for="password" required>Password</Label>
								<button
									type="button"
									class="text-xs font-medium text-brand-700 hover:text-brand-800"
									tabindex="-1"
									@click="toast.info('Use the reset link from your welcome email, or contact support.')"
								>
									Forgot?
								</button>
							</div>
							<div class="relative">
								<Lock class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
								<Input
									id="password"
									v-model="password"
									:type="showPassword ? 'text' : 'password'"
									autocomplete="current-password"
									placeholder="••••••••"
									:disabled="busy"
									class="h-11 pl-10 pr-10"
								/>
								<button
									type="button"
									class="absolute inset-y-0 right-0 flex items-center px-3 text-gray-400 transition-colors hover:text-brand-700"
									:aria-label="showPassword ? 'Hide password' : 'Show password'"
									tabindex="-1"
									@click="showPassword = !showPassword"
								>
									<EyeOff v-if="showPassword" class="h-4 w-4" />
									<Eye v-else class="h-4 w-4" />
								</button>
							</div>
						</div>

						<Button type="submit" class="w-full" size="lg" :loading="busy">
							<span>{{ busy ? "Signing in…" : "Sign in" }}</span>
							<ArrowRight v-if="!busy" class="h-4 w-4" />
						</Button>
					</form>

					<div class="mt-6 flex items-center justify-center gap-1.5 text-xs text-gray-400">
						<ShieldCheck class="h-3.5 w-3.5 text-emerald-500" />
						<span>Secure, encrypted sign-in</span>
					</div>
					<p class="mt-2 text-center text-xs text-gray-400">
						Trouble signing in? Contact your administrator.
					</p>
				</div>

				<!-- Phase 2 — Operator / Desk chooser (only when the role has both homes) -->
				<div v-else class="rounded-3xl border border-gray-100 bg-white/95 p-8 shadow-[0_28px_70px_-32px_rgba(184,134,11,0.35)] backdrop-blur-sm">
					<div class="mb-6 space-y-2">
						<span class="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-700">
							<span class="h-px w-5 bg-brand-300"></span> Signed in
						</span>
						<h1 class="text-[27px] font-bold leading-tight tracking-tight text-gray-900">
							Welcome{{ firstName ? ', ' + firstName : '' }}
						</h1>
						<p class="text-sm text-gray-500">Where would you like to go?</p>
					</div>

					<div class="space-y-3">
						<button
							type="button"
							class="group flex w-full items-center gap-3 rounded-2xl border border-gray-200 p-4 text-left transition-colors hover:border-brand-300 hover:bg-brand-50/40"
							@click="goOperator"
						>
							<span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-100 text-brand-700">
								<LayoutDashboard class="h-5 w-5" />
							</span>
							<span class="min-w-0 flex-1">
								<span class="block font-semibold text-gray-900">Operator App</span>
								<span class="block text-xs text-gray-500">Day-to-day — containers, shipments, customers, billing</span>
							</span>
							<ArrowRight class="h-4 w-4 shrink-0 text-gray-300 transition-colors group-hover:text-brand-600" />
						</button>

						<button
							v-if="dest?.has_desk"
							type="button"
							class="group flex w-full items-center gap-3 rounded-2xl border border-gray-200 p-4 text-left transition-colors hover:border-brand-300 hover:bg-brand-50/40"
							@click="goDesk"
						>
							<span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gray-100 text-gray-600">
								<Wrench class="h-5 w-5" />
							</span>
							<span class="min-w-0 flex-1">
								<span class="block font-semibold text-gray-900">Desk</span>
								<span class="block text-xs text-gray-500">Full admin — accounting, settings, configuration</span>
							</span>
							<ArrowRight class="h-4 w-4 shrink-0 text-gray-300 transition-colors group-hover:text-brand-600" />
						</button>
					</div>

					<button
						type="button"
						class="mt-5 w-full text-center text-xs font-medium text-gray-400 transition-colors hover:text-brand-700"
						@click="goBack"
					>
						Back to website
					</button>
				</div>

				<p class="mt-5 text-center text-[11px] text-gray-400">
					Developed by
					<span class="font-medium text-gray-500">Build With Moi</span>
				</p>
			</div>
		</section>
	</div>
</template>

<style>
/* The brand panel's right edge is sculpted by the SVG clipPath defined inline
   at the top of the template. Only applied at lg+ because the mobile layout
   stacks instead of splitting. */
@media (min-width: 1024px) {
	.bwm-brand-panel {
		-webkit-clip-path: url(#bwmBrandCurve);
		clip-path: url(#bwmBrandCurve);
	}
}

/* Chip used in the hero feature list. */
.bwm-chip {
	display: inline-flex;
	align-items: center;
	gap: 0.5rem;
	border-radius: 9999px;
	background-color: rgba(255, 255, 255, 0.1);
	padding: 0.375rem 1rem;
	font-size: 0.875rem;
	-webkit-backdrop-filter: blur(8px);
	backdrop-filter: blur(8px);
	box-shadow: inset 0 0 0 1px rgba(227, 184, 74, 0.35);
}

/* Floating blurred orbs — slow gold drift over black for depth without imagery. */
.bwm-blob {
	position: absolute;
	border-radius: 9999px;
	filter: blur(70px);
	opacity: 0.4;
	mix-blend-mode: screen;
	will-change: transform;
}
.bwm-blob-a {
	width: 30rem;
	height: 30rem;
	top: -8rem;
	left: -6rem;
	background: radial-gradient(circle at 30% 30%, #f7e8b8, transparent 65%);
	animation: bwm-float-a 22s ease-in-out infinite;
}
.bwm-blob-b {
	width: 26rem;
	height: 26rem;
	bottom: -6rem;
	right: -4rem;
	background: radial-gradient(circle at 60% 50%, #d4a12b, transparent 70%);
	animation: bwm-float-b 28s ease-in-out infinite;
}
.bwm-blob-c {
	width: 22rem;
	height: 22rem;
	top: 35%;
	left: 50%;
	transform: translate(-50%, -50%);
	background: radial-gradient(circle at 50% 50%, #e3b84a, transparent 70%);
	animation: bwm-float-c 35s ease-in-out infinite;
}
@keyframes bwm-float-a {
	0%, 100% { transform: translate(0, 0) scale(1); }
	50% { transform: translate(40px, 60px) scale(1.1); }
}
@keyframes bwm-float-b {
	0%, 100% { transform: translate(0, 0) scale(1); }
	50% { transform: translate(-50px, -40px) scale(1.05); }
}
@keyframes bwm-float-c {
	0%, 100% { transform: translate(-50%, -50%) scale(1); }
	50% { transform: translate(-45%, -60%) scale(1.15); }
}

/* Twinkle dots layered over the black ground. */
.bwm-sparkle {
	position: absolute;
	width: 6px;
	height: 6px;
	border-radius: 9999px;
	background: #e3b84a;
	box-shadow: 0 0 12px 2px rgba(227, 184, 74, 0.7);
	opacity: 0;
	animation: bwm-twinkle 3.4s ease-in-out infinite;
}
@keyframes bwm-twinkle {
	0%, 100% { opacity: 0; transform: scale(0.6); }
	50% { opacity: 0.9; transform: scale(1); }
}

/* Form entry. */
.bwm-form-enter {
	animation: bwm-form-rise 0.55s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes bwm-form-rise {
	0% { opacity: 0; transform: translateY(14px); }
	100% { opacity: 1; transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
	.bwm-blob, .bwm-sparkle, .bwm-form-enter {
		animation: none !important;
	}
}
</style>
