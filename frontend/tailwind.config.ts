import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

export default {
	darkMode: ["class"],
	content: ["./index.html", "./src/**/*.{vue,ts,tsx,js,jsx}"],
	theme: {
		container: {
			center: true,
			padding: "1.5rem",
			screens: { "2xl": "1400px" },
		},
		extend: {
			fontFamily: {
				// Clean system-UI stack for crisp, legible body + UI text
				// (no network webfonts that could be blocked). Headings reuse
				// the same family with tighter tracking for a calm, premium feel.
				sans: [
					"ui-sans-serif",
					"system-ui",
					"-apple-system",
					"BlinkMacSystemFont",
					"Segoe UI",
					"Roboto",
					"Helvetica Neue",
					"Arial",
					"sans-serif",
				],
			},
			colors: {
				// Gold brand ramp — the single accent of the gold/black/white
				// identity. brand-600 is the primary CTA; gold is never used
				// for body text on white (contrast rule from the PRD §6.5).
				brand: {
					50: "#fdfaee",
					100: "#faf2d4",
					200: "#f4e3a8",
					300: "#eccf72",
					400: "#e3b84a",
					500: "#d4a12b",
					600: "#b8860b",
					700: "#96690a",
					800: "#7a540e",
					900: "#654510",
				},
				// Near-black nav surface (replaces ex_beauty's navy) as a scale
				// so hovers/borders on the bar stay cohesive.
				coal: {
					700: "#1d1d1f",
					800: "#161617",
					900: "#0f0f10",
				},
				border: "hsl(var(--border))",
				input: "hsl(var(--input))",
				ring: "hsl(var(--ring))",
				background: "hsl(var(--background))",
				foreground: "hsl(var(--foreground))",
				primary: {
					DEFAULT: "hsl(var(--primary))",
					foreground: "hsl(var(--primary-foreground))",
				},
				secondary: {
					DEFAULT: "hsl(var(--secondary))",
					foreground: "hsl(var(--secondary-foreground))",
				},
				destructive: {
					DEFAULT: "hsl(var(--destructive))",
					foreground: "hsl(var(--destructive-foreground))",
				},
				muted: {
					DEFAULT: "hsl(var(--muted))",
					foreground: "hsl(var(--muted-foreground))",
				},
				accent: {
					DEFAULT: "hsl(var(--accent))",
					foreground: "hsl(var(--accent-foreground))",
				},
				popover: {
					DEFAULT: "hsl(var(--popover))",
					foreground: "hsl(var(--popover-foreground))",
				},
				card: {
					DEFAULT: "hsl(var(--card))",
					foreground: "hsl(var(--card-foreground))",
				},
			},
			borderRadius: {
				lg: "var(--radius)",
				md: "calc(var(--radius) - 2px)",
				sm: "calc(var(--radius) - 4px)",
			},
			boxShadow: {
				// Soft, small shadows. `card` is the resting elevation for
				// surfaces; `pop` for menus/dropdowns; `modal` for dialogs.
				// Kept low-opacity and tight for a calm feel.
				xs: "0 1px 2px 0 rgb(26 22 12 / 0.04)",
				card: "0 1px 2px 0 rgb(26 22 12 / 0.05), 0 1px 3px 0 rgb(26 22 12 / 0.04)",
				pop: "0 4px 12px -2px rgb(26 22 12 / 0.10), 0 2px 6px -2px rgb(26 22 12 / 0.06)",
				modal: "0 16px 48px -12px rgb(26 22 12 / 0.24), 0 4px 12px -4px rgb(26 22 12 / 0.10)",
			},
		},
	},
	plugins: [animate],
} satisfies Config;
