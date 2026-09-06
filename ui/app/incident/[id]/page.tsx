import Link from "next/link";
import { notFound } from "next/navigation";

import { DiffView } from "@/components/DiffView";
import { GovernorGauntlet } from "@/components/GovernorGauntlet";
import { Section } from "@/components/Section";
import { StateBadge } from "@/components/StateBadge";
import { TierBadge } from "@/components/TierBadge";
import { TraceDivergence } from "@/components/TraceDivergence";
import { Verification } from "@/components/Verification";
import { loadIncident, loadIncidents, testFile, testName } from "@/lib/incidents";

export function generateStaticParams() {
  return loadIncidents().map((incident) => ({ id: incident.incident_id }));
}

const CLASSIFICATIONS: Record<string, string> = {
  CAUSALLY_SUFFICIENT: "reproduces the failure every time it is forced",
  NECESSARY_INSUFFICIENT: "reproduces it sometimes — necessary, but not on its own",
  IRRELEVANT: "does not reproduce the failure; noise",
  INFEASIBLE: "this ordering cannot occur in this code",
  UNTESTED: "not forced (an earlier candidate already decided it)",
  SUSPICIOUS: "correlated, not yet tested",
};

export default function IncidentPage({ params }: { params: { id: string } }) {
  const incident = loadIncident(params.id);
  if (!incident) notFound();

  const inversion =
    incident.diagnosis.proven_inversion ?? incident.diagnosis.candidates[0] ?? null;

  return (
    <article>
      {/* 1 — verdict */}
      <div
        className="mb-8 rounded border border-border bg-surface p-6"
        aria-live="polite"
      >
        <div className="mb-4 flex flex-wrap items-center gap-4">
          <StateBadge state={incident.ui_state} large />
          {incident.verification && <TierBadge tier={incident.verification.tier_reached} />}
        </div>
        <h1 className="mb-1 font-mono text-xl">{testName(incident.test_id)}</h1>
        <p className="mb-4 text-sm text-muted">
          {testFile(incident.test_id)} · failed in{" "}
          {(incident.natural_flake_rate * 100).toFixed(0)}% of captured runs
          {incident.probe_effect_delta !== null && (
            <>
              {" "}· instrumentation shifted that rate by{" "}
              {(incident.probe_effect_delta * 100).toFixed(0)} points, reported rather than hidden
            </>
          )}
        </p>
        <p className="max-w-3xl">{incident.diagnosis.explanation}</p>
        {incident.intent && incident.intent.rationale && (
          <p className="mt-3 max-w-3xl text-sm text-muted">{incident.intent.rationale}</p>
        )}
      </div>

      {/* 2 — divergence */}
      <Section
        title="Where the two runs diverge"
        subtitle="The same test, twice, on a shared time axis. The outlined pair is the ordering that differs."
      >
        <TraceDivergence
          passLane={incident.pass_lane}
          failLane={incident.fail_lane}
          inverted={inversion?.failing_order ?? []}
        />
      </Section>

      {/* 3 — evidence */}
      <Section
        title="Evidence"
        subtitle="Suspicion comes from comparing runs. The decision comes from forcing the ordering and seeing what happens."
      >
        {incident.diagnosis.candidates.length === 0 ? (
          <p className="text-sm text-muted">
            No ordering differed between the passing and failing runs.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                  <th className="py-2 pr-4 font-normal">Ordering</th>
                  <th className="py-2 pr-4 font-normal" title="Ochiai suspiciousness">
                    Suspiciousness
                  </th>
                  <th className="py-2 pr-4 font-normal">When forced</th>
                  <th className="py-2 font-normal">Verdict</th>
                </tr>
              </thead>
              <tbody>
                {incident.diagnosis.candidates.map((candidate) => (
                  <tr key={candidate.failing_order.join()} className="border-b border-border/60">
                    <td className="py-3 pr-4 font-mono text-xs">
                      {candidate.failing_order.join("  →  ")}
                      {candidate.in_backward_slice && (
                        <span className="ml-2 text-[11px] text-muted">
                          the assertion depends on this
                        </span>
                      )}
                    </td>
                    <td className="py-3 pr-4 font-mono">{candidate.ochiai_score.toFixed(2)}</td>
                    <td className="py-3 pr-4 font-mono">
                      {candidate.forced_failure_rate === null
                        ? "—"
                        : `fails ${(candidate.forced_failure_rate * 100).toFixed(0)}%`}
                    </td>
                    <td className="py-3 text-xs text-muted">
                      {CLASSIFICATIONS[candidate.classification] ?? candidate.classification}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {incident.diagnosis.bug_depth && (
          <p className="mt-4 text-sm text-muted">
            One scheduling constraint is enough to reproduce this failure.
          </p>
        )}
        {incident.diagnosis.abstain_reason === "DEPTH_GE_2_UNRESOLVED" && (
          <p className="mt-4 rounded border border-warn/40 bg-warn/10 p-3 text-sm text-warn">
            No single ordering reproduces this failure on its own, so it needs at least two
            scheduling constraints at once. ChronoTrace reports that rather than patching the
            nearest symptom.
          </p>
        )}
      </Section>

      {/* 4 — governor */}
      <Section
        title="Policy gate"
        subtitle="Every check the proposed patch had to pass before it was allowed to run."
      >
        <GovernorGauntlet verdict={incident.verdict} rejected={incident.rejected_attempts} />
      </Section>

      {/* 5 — verification */}
      <Section
        title="Verification"
        subtitle="What was established, and at which strength. A weaker check is never presented as proof."
      >
        <Verification
          result={incident.verification}
          regressionPath={incident.regression_test_path}
          regressionVerified={incident.regression_verified}
        />
      </Section>

      {incident.unified_diff && (
        <Section
          title="Proposed change"
          subtitle="Nothing is merged automatically. This is a diff for a human to review."
        >
          <DiffView diff={incident.unified_diff} />
        </Section>
      )}

      <Link href="/" className="text-sm text-accent">
        ← All incidents
      </Link>
    </article>
  );
}
