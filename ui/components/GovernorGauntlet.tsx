"use client";

import { motion, useReducedMotion } from "framer-motion";

import { motionTokens } from "@/lib/motion";
import type { GovernorVerdict } from "@/lib/types";

// Plain language in the interface, rule ids in the tooltip. A reader should not
// need the specification open to understand what was checked.
const GROUPS: Record<string, string> = {
  N: "Refused shortcuts",
  P: "Required substance",
  S: "Structural safety",
};

export function GovernorGauntlet({
  verdict,
  rejected,
}: {
  verdict: GovernorVerdict | null;
  rejected: GovernorVerdict[];
}) {
  const reduced = useReducedMotion();
  const shown = verdict ?? rejected[0] ?? null;
  if (!shown) {
    return (
      <p className="text-sm text-muted">
        No patch was proposed, so there was nothing for the policy gate to review.
      </p>
    );
  }
  const groups = Object.entries(GROUPS).map(([prefix, title]) => ({
    title,
    rules: shown.rules_evaluated.filter((rule) => rule.rule_id.startsWith(prefix)),
  }));
  const failed = shown.rules_evaluated.filter((rule) => !rule.passed);

  return (
    <div>
      <p className="mb-4 text-sm text-muted">
        {shown.approved
          ? `All ${shown.rules_evaluated.length} checks passed. A patch runs only when every one of them does.`
          : `${failed.length} of ${shown.rules_evaluated.length} checks failed, so this patch was never applied.`}
      </p>
      <div className="grid gap-6 sm:grid-cols-3">
        {groups.map((group, groupIndex) => (
          <div key={group.title}>
            <h3 className="mb-2 text-xs uppercase tracking-wide text-muted">{group.title}</h3>
            <ul className="space-y-2">
              {group.rules.map((rule, ruleIndex) => (
                <motion.li
                  key={rule.rule_id}
                  initial={reduced ? false : { opacity: 0, y: 4 }}
                  animate={
                    rule.passed
                      ? { opacity: 1, y: 0 }
                      : { opacity: 1, y: 0, x: reduced ? 0 : [0, -8, 8, 0] }
                  }
                  transition={{
                    duration: motionTokens.instant,
                    ease: motionTokens.ease,
                    delay: reduced ? 0 : (groupIndex * 5 + ruleIndex) * 0.06,
                  }}
                  className={`flex items-start gap-2 rounded border px-3 py-2 text-sm ${
                    rule.passed
                      ? "border-border bg-surface text-text"
                      : "border-fail/50 bg-fail/10 text-fail"
                  }`}
                  title={`Rule ${rule.rule_id}`}
                >
                  <span aria-hidden="true">{rule.passed ? "✓" : "✕"}</span>
                  <span>
                    {rule.description}
                    {!rule.passed && rule.detail ? (
                      <span className="mt-1 block text-xs opacity-90">{rule.detail}</span>
                    ) : null}
                  </span>
                </motion.li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
