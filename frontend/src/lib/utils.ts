import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

// shadcn-vue helper: merge Tailwind class strings safely, deduping conflicting
// utilities (e.g. `px-2 px-4` collapses to `px-4`). Used by every UI primitive.
export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}
