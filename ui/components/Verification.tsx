"use client";

import { motion, useReducedMotion } from "framer-motion";

import { motionTokens } from "@/lib/motion";
import type { VerificationResult } from "@/lib/types";

function TierRow({
  title,
  detail,
  state,
}: {
  title: string;
  detail: string;
  state: "pass" | "fail" | "skipped";
}) {
  const icon = state === "pass" ? "✓" : state === "fail" ? "✕" : "—";
  const tone =
    state === "pass" ? "text-pass" : state === "fail" ? "text-fail" : "text-muted";
  return (
    <li className="flex items-start gap-3 border-b border-border py-3 last:border-0">
      <span className={`font-mono ${tone}`} aria-hidden="true">
        {icon}
      </span>
      <div>
        <p className="text-sm">{title}</p>
        <p className="text-xs text-muted">{detail}</p>
      </div>
    </li>
  );
}

export function Verification({
  result,
  regressionPath,
  regressionVerified,
}: {
  result: VerificationResult | null;
  regressionPath: string | null;
  regressionVerified: boolean;
}) {
  const reduced = useReducedMotion();
  if (!result) {
    return (
      <p className="text-sm text-muted">
        Verification did not run: no patch reached it.
      </p>
    );
  }
  const stable = result.statistical_runs - result.statistical_failures;
  return (
    <div>
      <ul className="mb-6 list-none p-0">
        <TierRow
          title="Reproduced the exact interleaving on demand"
          detail={
            result.pre_patch_forced_failed === null
              ? "not attempted"
              : result.post_patch_forced_infeasible
                ? "before the fix it failed every time under the forced ordering; after the fix that ordering can no longer be produced at all"
                : `before the fix it failed every time under the forced ordering; after the fix it passed every time under the identical ordering (${
                    result.post_patch_forced_passed ? "confirmed" : "not confirmed"
                  })`
          }
          state={
            result.pre_patch_forced_failed &&
            (result.post_patch_forced_passed || result.post_patch_forced_infeasible)
              ? "pass"
              : result.pre_patch_forced_failed === null
                ? "skipped"
                : "fail"
          }
        />
        <TierRow
          title="Adversarial schedules"
          detail={
            result.pct_runs === 0
              ? "not attempted for this incident, and so not claimed"
              : `${result.pct_runs - result.pct_failures} of ${result.pct_runs} scheduled runs held`
          }
          state={result.pct_runs === 0 ? "skipped" : result.pct_failures === 0 ? "pass" : "fail"}
        />
        <TierRow
          title="Residual flake check"
          detail={`${stable} of ${result.statistical_runs} ordinary runs stable, against ${result.pre_patch_natural_failures} failures in the same number of runs before the fix`}
          state={result.statistical_failures === 0 ? "pass" : "fail"}
        />
      </ul>

      <div
        className="mb-6 flex flex-wrap gap-1"
        role="img"
        aria-label={`${stable} of ${result.statistical_runs} repeat runs passed after the fix`}
      >
        {Array.from({ length: result.statistical_runs }).map((_, index) => (
          <motion.span
            key={index}
            initial={reduced ? false : { opacity: 0, scale: 0.6 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{
              duration: motionTokens.instant,
              ease: motionTokens.ease,
              delay: reduced ? 0 : index * 0.018,
            }}
            className={`h-3 w-3 rounded-[2px] ${
              index < stable ? "bg-pass" : "bg-fail"
            }`}
          />
        ))}
      </div>

      {result.symptom_patch_suspected && (
        <p className="mb-4 rounded border border-warn/40 bg-warn/10 p-3 text-sm text-warn">
          The targeted interleaving is blocked but repeat runs still fail. That is the signature
          of a patched symptom rather than a fixed cause, and it is reported rather than hidden.
        </p>
      )}

      <dl className="grid gap-4 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted">Measured overhead</dt>
          <dd className="font-mono">
            {result.measured_overhead_ms >= 0 ? "+" : ""}
            {result.measured_overhead_ms} ms
            <span className="ml-2 text-xs text-muted">no fixed delay introduced</span>
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted">Isolation</dt>
          <dd className="font-mono">one {result.isolation} per run</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-xs uppercase tracking-wide text-muted">Reproduction seed</dt>
          <dd className="font-mono text-xs">
            {Object.entries(result.reproduction_seed).map(([key, value]) => (
              <span key={key} className="mr-4 inline-block">
                <span className="text-muted">{key}</span> {value}
              </span>
            ))}
          </dd>
        </div>
        {regressionPath && (
          <div className="sm:col-span-2">
            <dt className="text-xs uppercase tracking-wide text-muted">
              Regression guard {regressionVerified ? "(executed and confirmed)" : "(emitted)"}
            </dt>
            <dd className="break-all font-mono text-xs text-accent">{regressionPath}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}
