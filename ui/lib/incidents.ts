import fs from "node:fs";
import path from "node:path";

import type { IncidentReport } from "./types";

// Incidents are exported by `chronotrace eval` (registry.store.export). The
// dashboard reads a file rather than calling a service, so the demo cannot
// stall on a network round-trip.
const CANDIDATES = [
  path.join(process.cwd(), "..", "eval-results", "incidents.json"),
  path.join(process.cwd(), "public", "incidents.json"),
];

export function loadIncidents(): IncidentReport[] {
  for (const candidate of CANDIDATES) {
    if (fs.existsSync(candidate)) {
      return JSON.parse(fs.readFileSync(candidate, "utf8")) as IncidentReport[];
    }
  }
  return [];
}

export function loadIncident(id: string): IncidentReport | undefined {
  return loadIncidents().find((incident) => incident.incident_id === id);
}

export function testName(testId: string): string {
  return testId.split("::").pop() ?? testId;
}

export function testFile(testId: string): string {
  const file = testId.split("::")[0];
  return file.split("/").pop() ?? file;
}
