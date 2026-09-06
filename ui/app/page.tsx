import Link from "next/link";

import { StateBadge } from "@/components/StateBadge";
import { TierBadge } from "@/components/TierBadge";
import { loadIncidents, testFile, testName } from "@/lib/incidents";

export default function IncidentList() {
  const incidents = loadIncidents();

  if (incidents.length === 0) {
    return (
      <div className="rounded border border-border bg-surface p-6">
        <h1 className="mb-2 text-lg font-medium">No incidents yet</h1>
        <p className="text-sm text-muted">
          Run <code className="font-mono text-accent">uv run chronotrace eval --arm C</code> from
          the repository root. It writes <code className="font-mono">eval-results/incidents.json</code>,
          which this dashboard reads directly — no service, no network round-trip.
        </p>
      </div>
    );
  }

  const fixed = incidents.filter((incident) => incident.ui_state === "FIXED").length;
  const abstained = incidents.filter((incident) => incident.ui_state === "ABSTAINED").length;

  return (
    <div>
      <h1 className="mb-1 text-2xl font-medium">Incidents</h1>
      <p className="mb-6 text-sm text-muted">
        {incidents.length} flaky tests investigated · {fixed} repaired and verified · {abstained}{" "}
        deliberately refused
      </p>
      <ul className="list-none space-y-2 p-0">
        {incidents.map((incident) => (
          <li key={incident.incident_id}>
            <Link
              href={`/incident/${incident.incident_id}`}
              className="flex flex-wrap items-center gap-4 rounded border border-border bg-surface p-4 transition-colors hover:border-accent/50"
            >
              <StateBadge state={incident.ui_state} />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-mono text-sm">
                  {testName(incident.test_id)}
                </span>
                <span className="block truncate text-xs text-muted">
                  {testFile(incident.test_id)} · flaky in{" "}
                  {(incident.natural_flake_rate * 100).toFixed(0)}% of captured runs
                </span>
              </span>
              {incident.verification && <TierBadge tier={incident.verification.tier_reached} />}
              <span className="font-mono text-xs text-muted">{incident.incident_id}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
