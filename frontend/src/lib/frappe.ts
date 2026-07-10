// Thin Frappe client — fetch + CSRF + uniform error shape.
//
// Why not frappe-ui? The only piece we'd use is `call`, which is ~20 lines.
// Bigger primitives (resource caching, list pagination) can be added when we
// hit a use case.
//
// CSRF: the www/logistics.html template sets `window.csrf_token`; Frappe
// rejects POSTs without `X-Frappe-CSRF-Token` for non-Guest sessions.

declare global {
	interface Window {
		csrf_token?: string;
	}
}

export class FrappeApiError extends Error {
	constructor(
		message: string,
		public status: number,
		public payload?: unknown,
	) {
		super(message);
		this.name = "FrappeApiError";
	}
}

export async function call<T = unknown>(
	method: string,
	args: Record<string, unknown> = {},
): Promise<T> {
	const headers: Record<string, string> = {
		"Content-Type": "application/json",
		Accept: "application/json",
		"X-Requested-With": "XMLHttpRequest",
	};
	if (window.csrf_token) {
		headers["X-Frappe-CSRF-Token"] = window.csrf_token;
	}

	const res = await fetch(`/api/method/${encodeURI(method)}`, {
		method: "POST",
		credentials: "same-origin",
		headers,
		body: JSON.stringify(args),
	});

	let body: unknown = null;
	const text = await res.text();
	if (text) {
		try {
			body = JSON.parse(text);
		} catch {
			body = text;
		}
	}

	if (res.status === 401) {
		// Session expired — reload the SPA shell so www/logistics.html
		// re-renders the branded login with a fresh CSRF token.
		const next = encodeURIComponent(window.location.pathname + window.location.search);
		window.location.href = `/logistics?redirect-to=${next}`;
		throw new FrappeApiError("Session expired", 401, body);
	}

	if (!res.ok) {
		// Frappe returns errors as { exception, exc_type, _server_messages } —
		// _server_messages is a JSON string containing the user-friendly text.
		const message = extractMessage(body) || res.statusText || "Request failed";
		throw new FrappeApiError(message, res.status, body);
	}

	// Successful Frappe responses look like { message: ... }. Unwrap if so;
	// otherwise return the raw body (some endpoints return arrays directly).
	if (body && typeof body === "object" && "message" in body) {
		return (body as { message: T }).message;
	}
	return body as T;
}

// Upload a file via Frappe's upload_file endpoint and return its URL.
// multipart/form-data — let the browser set the boundary, so we don't send
// a Content-Type header.
export async function uploadFile(
	file: File,
	opts: { isPrivate?: boolean } = {},
): Promise<string> {
	const fd = new FormData();
	fd.append("file", file, file.name);
	fd.append("is_private", opts.isPrivate ? "1" : "0");
	fd.append("folder", "Home");

	const headers: Record<string, string> = { Accept: "application/json" };
	if (window.csrf_token) headers["X-Frappe-CSRF-Token"] = window.csrf_token;

	const res = await fetch("/api/method/upload_file", {
		method: "POST",
		credentials: "same-origin",
		headers,
		body: fd,
	});
	const body = await res.json().catch(() => null);
	if (!res.ok) {
		throw new FrappeApiError(extractMessage(body) || "Upload failed", res.status, body);
	}
	return (body as { message: { file_url: string } }).message.file_url;
}

function extractMessage(body: unknown): string | null {
	if (!body || typeof body !== "object") return null;
	const b = body as { _server_messages?: string; exception?: string; message?: unknown };
	if (b._server_messages) {
		try {
			const arr = JSON.parse(b._server_messages) as string[];
			const first = arr.length ? JSON.parse(arr[0]) : null;
			if (first && typeof first === "object" && "message" in first) {
				return (first as { message: string }).message;
			}
		} catch {
			/* fall through */
		}
	}
	if (b.exception) return b.exception;
	if (typeof b.message === "string") return b.message;
	return null;
}
