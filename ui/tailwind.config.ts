import type { Config } from "tailwindcss";

// Every token comes from the design specification. No inline magic numbers.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        border: "var(--border)",
        text: "var(--text)",
        muted: "var(--muted)",
        accent: "var(--accent)",
        pass: "var(--pass)",
        fail: "var(--fail)",
        warn: "var(--warn)",
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      borderRadius: { DEFAULT: "8px", lg: "8px" },
      spacing: { 1: "4px", 2: "8px", 3: "12px", 4: "16px", 6: "24px", 8: "32px", 12: "48px" },
    },
  },
  plugins: [],
};
export default config;
