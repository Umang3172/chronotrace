import fs from "node:fs";
import path from "node:path";

interface Score {
  arm: string;
  provider: string;
  cases_run: number;
  repair_rate: number | null;
  false_repair_rate: number | null;
  abstention_accuracy: number | null;
  causal_precision: number | null;
  band_aid_rate: number | null;
  tokens_per_repair: number | null;
  median_overhead_ms: number | null;
  tier_counts: Record<string, number>;
}

interface Results {
  arms: { arm: string; provider: string; skipped_reason: string | null }[];
  scores: Score[];
}

function loadResults(): Results | null {
  const target = path.join(process.cwd(), "..", "eval-results", "results.json");
  if (!fs.existsSync(target)) return null;
  return JSON.parse(fs.readFileSync(target, "utf8")) as Results;
}

const percent = (value: number | null) => (value === null ? "n/a" : `${Math.round(value * 100)}%`);

function Bar({ value, tone }: { value: number | null; tone: "good" | "bad" }) {
  if (value === null) return <span className="text-muted">n/a</span>;
  return (
    <div className="flex items-center gap-3">
      <div
        className="h-2 w-32 overflow-hidden rounded-full bg-border"
        role="img"
        aria-label={percent(value)}
      >
        <div
          className={`h-full rounded-full ${tone === "good" ? "bg-pass" : "bg-fail"}`}
          style={{ width: `${Math.max(value * 100, value > 0 ? 2 : 0)}%` }}
        />
      </div>
      <span className="font-mono text-sm">{percent(value)}</span>
    </div>
  );
}

// Tier names as they read to someone who has not read the specification.
const TIER_LABELS: Record<string, string> = {
  FORCED: "reproduced on demand",
  INFEASIBLE: "ordering unreachable",
  PCT: "adversarial schedules",
  STATISTICAL: "repeat runs only",
  FAILED: "not verified",
  NOT_REACHED: "no patch reached verification",
};

export default function EvalPage() {
  const results = loadResults();
  if (!results) {
    return (
      <div className="rounded border border-border bg-surface p-6">
        <h1 className="mb-2 text-lg font-medium">No results yet</h1>
        <p className="text-sm text-muted">
          Run <code className="font-mono text-accent">uv run chronotrace eval --arm all</code>.
          Every number on this page comes from that command; none is entered by hand.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="mb-1 text-2xl font-medium">Results</h1>
      <p className="mb-6 max-w-3xl text-sm text-muted">
        Seeded benchmark, produced by <code className="font-mono">chronotrace eval</code>. The
        corpus is written for this project rather than mined from the wild, so this is a
        controlled comparison on identical inputs — a directional effect, not a population
        estimate.
      </p>

      {results.scores.map((score) => (
        <section key={score.arm} className="mb-6 rounded border border-border bg-surface p-6">
          <h2 className="mb-1 text-lg font-medium">Arm {score.arm}</h2>
          <p className="mb-4 text-sm text-muted">
            {score.cases_run} cases · provider <code className="font-mono">{score.provider}</code>
          </p>
          <dl className="grid gap-4 sm:grid-cols-2">
            <div>
              <dt className="mb-1 text-xs uppercase tracking-wide text-muted">
                Repaired and verified
              </dt>
              <dd>
                <Bar value={score.repair_rate} tone="good" />
              </dd>
            </div>
            <div>
              <dt className="mb-1 text-xs uppercase tracking-wide text-muted">
                Wrongly patched a non-race
              </dt>
              <dd>
                <Bar value={score.false_repair_rate} tone="bad" />
              </dd>
            </div>
            <div>
              <dt className="mb-1 text-xs uppercase tracking-wide text-muted">
                Refused correctly when it should
              </dt>
              <dd>
                <Bar value={score.abstention_accuracy} tone="good" />
              </dd>
            </div>
            <div>
              <dt className="mb-1 text-xs uppercase tracking-wide text-muted">
                Timing band-aids introduced
              </dt>
              <dd>
                <Bar value={score.band_aid_rate} tone="bad" />
              </dd>
            </div>
            <div>
              <dt className="mb-1 text-xs uppercase tracking-wide text-muted">
                Proposed orderings that reproduced the failure
              </dt>
              <dd>
                <Bar value={score.causal_precision} tone="good" />
              </dd>
            </div>
            <div>
              <dt className="mb-1 text-xs uppercase tracking-wide text-muted">
                Measured overhead
              </dt>
              <dd className="font-mono text-sm">
                {score.median_overhead_ms === null ? "n/a" : `${score.median_overhead_ms} ms`}
                <span className="ml-2 text-xs text-muted">no fixed delay introduced</span>
              </dd>
            </div>
          </dl>
          <p className="mt-4 text-xs text-muted">
            Verification strength:{" "}
            {Object.entries(score.tier_counts)
              .map(([tier, count]) => `${TIER_LABELS[tier] ?? tier.toLowerCase()} ×${count}`)
              .join(", ")}
            {score.tokens_per_repair === null && (
              <>
                {" "}· token and cost figures are omitted for this provider rather than invented:
                the offline reference policy is not a model and has no tokens to report.
              </>
            )}
          </p>
        </section>
      ))}

      {results.arms
        .filter((arm) => arm.skipped_reason)
        .map((arm) => (
          <section
            key={arm.arm}
            className="mb-6 rounded border border-warn/40 bg-warn/10 p-6 text-sm text-warn"
          >
            <h2 className="mb-2 font-medium">Arm {arm.arm} did not run</h2>
            <p>{arm.skipped_reason}</p>
          </section>
        ))}
    </div>
  );
}
