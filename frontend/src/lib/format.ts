// Small display formatters shared across pages.

export function fmtDate(d?: string | null): string {
	if (!d) return "—";
	try {
		return new Date(d.replace(" ", "T")).toLocaleDateString(undefined, {
			day: "numeric",
			month: "short",
			year: "numeric",
		});
	} catch {
		return d;
	}
}

export function fmtDateTime(d?: string | null): string {
	if (!d) return "—";
	try {
		return new Date(d.replace(" ", "T")).toLocaleString(undefined, {
			day: "numeric",
			month: "short",
			hour: "2-digit",
			minute: "2-digit",
		});
	} catch {
		return d;
	}
}

export function fmtMoney(v?: number | null, currency?: string | null): string {
	if (v === null || v === undefined) return "—";
	const n = Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
	return currency ? `${currency} ${n}` : n;
}

export function fmtWeight(v?: number | null): string {
	if (!v) return "—";
	return `${Number(v).toLocaleString()} kg`;
}
