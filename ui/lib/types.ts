// Mirrors chronotrace/contracts.py. The Python models are the source of truth;
// these exist so the dashboard fails at compile time when they drift.

export type UiState = "FIXED" | "NEEDS_INVESTIGATION" | "ABSTAINED";

export type Tier = "FORCED" | "INFEASIBLE" | "PCT" | "STATISTICAL" | "FAILED";

export interface OperationRef {
  span_name: string;
  occurrence: number;
  source_file: string;
  source_line: number;
  qualname: string;
  is_test_scope: boolean;
  access: "read" | "write" | "unknown";
  resource: string | null;
}

export interface CandidateInversion {
  op_a: OperationRef;
  op_b: OperationRef;
  causal_position: number;
  ochiai_score: number;
  in_backward_slice: boolean;
  classification:
    | "UNTESTED"
    | "IRRELEVANT"
    | "SUSPICIOUS"
    | "NECESSARY_INSUFFICIENT"
    | "CAUSALLY_SUFFICIENT"
    | "INFEASIBLE";
  forced_failure_rate: number | null;
  failing_order: string[];
}

export interface Diagnosis {
  status: "RACE_PROVEN" | "NEEDS_INVESTIGATION" | "ABSTAINED";
  abstain_reason: string | null;
  proven_inversion: CandidateInversion | null;
  bug_depth: number | null;
  candidates_evaluated: number;
  candidates: CandidateInversion[];
  explanation: string;
}

export interface RuleOutcome {
  rule_id: string;
  description: string;
  passed: boolean;
  detail: string;
}

export interface GovernorVerdict {
  approved: boolean;
  negative_violations: string[];
  positive_check_passed: boolean;
  deadlock_cycle_detected: boolean;
  scope_violation: boolean;
  diff_checks: string[];
  rules_evaluated: RuleOutcome[];
}

export interface VerificationResult {
  tier_reached: Tier;
  pre_patch_forced_failed: boolean | null;
  post_patch_forced_passed: boolean | null;
  pct_runs: number;
  pct_failures: number;
  statistical_runs: number;
  statistical_failures: number;
  pre_patch_natural_failures: number;
  deadlock_detected: boolean;
  measured_overhead_ms: number;
  reproduction_seed: Record<string, string>;
  isolation: string;
  symptom_patch_suspected: boolean;
}

export interface RepairIntent {
  transformation: string;
  shared_scope: string;
  scope_target: string | null;
  signal_site: OperationRef | null;
  wait_site: OperationRef | null;
  primitive: string;
  rationale: string;
}

export interface LaneSpan {
  key: string;
  name: string;
  start_ms: number;
  duration_ms: number;
  task_name: string | null;
  source_line: number | null;
  access: string | null;
  in_inversion: boolean;
  is_assertion: boolean;
}

export interface TraceLane {
  outcome: "PASS" | "FAIL";
  run_id: string;
  total_ms: number;
  spans: LaneSpan[];
}

export interface IncidentReport {
  incident_id: string;
  test_id: string;
  ui_state: UiState;
  diagnosis: Diagnosis;
  intent: RepairIntent | null;
  verdict: GovernorVerdict | null;
  verification: VerificationResult | null;
  unified_diff: string | null;
  regression_test_path: string | null;
  regression_verified: boolean;
  natural_flake_rate: number;
  probe_effect_delta: number | null;
  pass_lane: TraceLane | null;
  fail_lane: TraceLane | null;
  rejected_attempts: GovernorVerdict[];
  tokens_input: number;
  tokens_output: number;
  llm_calls: number;
  wall_clock_s: number;
  provider: string;
}
