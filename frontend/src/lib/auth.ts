// Auth API wrappers — login/logout against Frappe's stock endpoints.
//
// Why not just hit /api/method/login from anywhere? Because that endpoint
// returns a Set-Cookie + `home_page` redirect hint; we want a consistent
// shape (`{ user }`) for the SPA and to surface the new session user from
// `/api/method/frappe.auth.get_logged_user` so the session store can update
// without a full reload.

import { call, FrappeApiError } from "./frappe";

export interface LoginResult {
	user: string;
	full_name?: string;
}

export interface LoginDestinations {
	user: string;
	full_name: string;
	has_operator: boolean;
	has_customer: boolean;
	has_desk: boolean;
}

export async function login(email: string, password: string): Promise<LoginResult> {
	// Frappe's /api/method/login expects `usr` + `pwd` (legacy field names).
	// It sets the sid cookie via Set-Cookie; subsequent calls inherit it.
	const res = await fetch("/api/method/login", {
		method: "POST",
		credentials: "same-origin",
		headers: {
			"Content-Type": "application/x-www-form-urlencoded",
			Accept: "application/json",
			"X-Requested-With": "XMLHttpRequest",
		},
		body: new URLSearchParams({ usr: email, pwd: password }).toString(),
	});

	const text = await res.text();
	let body: { message?: string; full_name?: string; home_page?: string } | null = null;
	try {
		body = text ? JSON.parse(text) : null;
	} catch {
		/* non-json error page */
	}

	if (!res.ok) {
		const msg = body?.message || "Invalid email or password";
		throw new FrappeApiError(msg, res.status, body);
	}

	// We deliberately don't refresh `window.csrf_token` here — the caller
	// does a full navigation right after, which re-renders www/logistics.html
	// and injects a fresh token into the bootstrap.
	const user = await call<string>("frappe.auth.get_logged_user");
	return {
		user,
		full_name: body?.full_name,
	};
}

export async function fetchDestinations(): Promise<LoginDestinations> {
	// GET (no CSRF needed) so it works with the freshly-issued session.
	const res = await fetch("/api/method/bwm_logistics.api.access.login_destinations", {
		credentials: "same-origin",
		headers: { Accept: "application/json" },
	});
	if (!res.ok) throw new FrappeApiError("Could not resolve destinations", res.status);
	return (await res.json()).message as LoginDestinations;
}

export async function logout(): Promise<void> {
	// /api/method/logout is POST-only and CSRF-protected for logged-in sessions,
	// so the token (injected by www/logistics.html) is required.
	const headers: Record<string, string> = { "X-Requested-With": "XMLHttpRequest" };
	if (window.csrf_token) headers["X-Frappe-CSRF-Token"] = window.csrf_token;
	await fetch("/api/method/logout", {
		method: "POST",
		credentials: "same-origin",
		headers,
	});
}
