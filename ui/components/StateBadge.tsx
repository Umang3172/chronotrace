import type { UiState } from "@/lib/types";

// Colour never carries meaning alone: every state has an icon and a text label
// so it survives colour-blindness and greyscale printing.
const STATES: Record<UiState, { label: string; icon: string; className: string }> = {
  FIXED: { label: "Fixed", icon: "✓", className: "text-pass border-pass/40 bg-pass/10" },
  NEEDS_INVESTIGATION: {
    label: "Needs investigation",
    icon: "◐",
    className: "text-warn border-warn/40 bg-warn/10",
  },
  ABSTAINED: { label: "Abstained", icon: "⊘", className: "text-muted border-border bg-surface" },
};

export function StateBadge({ state, large = false }: { state: UiState; large?: boolean }) {
  const meta = STATES[state];
  return (
    <span
      className={`inline-flex items-center gap-2 rounded border font-medium ${meta.className} ${
        large ? "px-4 py-2 text-base" : "px-2 py-1 text-xs"
      }`}
    >
      <span aria-hidden="true">{meta.icon}</span>
      {meta.label}
    </span>
  );
}
