import type { Tier } from "@/lib/types";

// The tier reached travels with every result. A lower tier is never presented
// as proof of causality, so the wording differs per tier by design.
const TIERS: Record<Tier, { label: string; claim: string; className: string }> = {
  FORCED_HARMLESS: {
    label: "Reproduced on demand",
    claim: "cause established — the ordering is now harmless",
    className: "text-pass border-pass/40 bg-pass/10",
  },
  FORCED_UNREACHABLE: {
    label: "Ordering eliminated",
    claim: "cause established — the ordering can no longer occur",
    className: "text-pass border-pass/40 bg-pass/10",
  },
  INFEASIBLE: {
    label: "Never reachable",
    claim: "candidate discarded — this ordering never occurred",
    className: "text-muted border-border bg-surface",
  },
  PCT: {
    label: "Adversarial schedules",
    claim: "probabilistic bound, not proof",
    className: "text-warn border-warn/40 bg-warn/10",
  },
  STATISTICAL: {
    label: "Repeat runs only",
    claim: "residual check, not proof",
    className: "text-warn border-warn/40 bg-warn/10",
  },
  FAILED: {
    label: "Not verified",
    claim: "no claim made",
    className: "text-fail border-fail/40 bg-fail/10",
  },
};

const UNKNOWN = {
  label: "Unrecognised verification tier",
  claim: "recorded by an older version",
  className: "text-muted border-border bg-surface",
};

export function TierBadge({ tier }: { tier: Tier }) {
  // Reports persisted by an earlier version can carry a tier this build no
  // longer knows. Render it plainly rather than crashing the page.
  const meta = TIERS[tier] ?? UNKNOWN;
  return (
    <span
      className={`inline-flex items-baseline gap-2 rounded border px-2 py-1 text-xs ${meta.className}`}
      title={meta.claim}
    >
      <span className="font-medium">{meta.label}</span>
      <span className="opacity-70">{meta.claim}</span>
    </span>
  );
}
