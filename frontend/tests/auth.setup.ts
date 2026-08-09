import { test as setup, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
	BASE_URL,
	STAFF_USER,
	STAFF_PWD,
	STORAGE_STATE,
	PORTAL_USER,
	PORTAL_PWD,
	PORTAL_STATE,
} from "../playwright.config";

// Logs in over the Frappe REST endpoint (no UI typing) and parks the session
// cookie in tests/.auth so every later spec starts already inside the app.
setup("authenticate staff", async ({ request }) => {
	const res = await request.post(`${BASE_URL}/api/method/login`, {
		data: { usr: STAFF_USER, pwd: STAFF_PWD },
	});
	expect(res.status(), `login failed for ${STAFF_USER}`).toBe(200);

	fs.mkdirSync(path.dirname(STORAGE_STATE), { recursive: true });
	await request.storageState({ path: STORAGE_STATE });
});

// A portal customer, so the leak test runs against the portal a customer sees
// rather than the operator dashboard a staff session is redirected to.
setup("authenticate portal customer", async ({ request }) => {
	const res = await request.post(`${BASE_URL}/api/method/login`, {
		data: { usr: PORTAL_USER, pwd: PORTAL_PWD },
	});
	expect(res.status(), `portal login failed for ${PORTAL_USER}`).toBe(200);
	fs.mkdirSync(path.dirname(PORTAL_STATE), { recursive: true });
	await request.storageState({ path: PORTAL_STATE });
});
