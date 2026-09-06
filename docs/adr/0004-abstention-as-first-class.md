# 4. Abstention is a first-class outcome

## Context

A trace diff over a concurrent program will always find *some* inversion. Tasks
interleave differently every run and almost none of it matters. A system built
to always return an answer will therefore confidently patch noise.

For a tool that modifies code, a wrong patch is worse than no patch: it buries
the real cause under a green build, and the next person to look has less
information than the first.

## Decision

`Diagnosis.status` is one of `RACE_PROVEN`, `NEEDS_INVESTIGATION` or
`ABSTAINED`, and abstention carries a specific machine-readable reason:
`NOT_A_RACE`, `NO_INVERSION`, `DEPTH_GE_2_UNRESOLVED`, `NO_TRACE_PAIR`,
`SPAN_GRANULARITY_TOO_COARSE`, `PRODUCTION_SCOPE_RACE`, `NON_ASYNCIO_PARADIGM`,
`THIRD_PARTY_CODE`.

The benchmark contains negative controls — tests whose flakiness has nothing to
do with scheduling — and the false-repair rate on them is a headline metric,
reported alongside the repair rate rather than beneath it.

## Consequences

- The repair rate is lower than it could be, deliberately.
- Abstention reasons are surfaced in plain language in the UI, so a refusal is
  actionable rather than a shrug.
- The benchmark cannot be accused of being designed around the algorithm: seven
  of its fourteen cases are ones the system must refuse.

## Alternatives considered

- **Confidence score on every diagnosis.** Rejected: the draft specification
  contained a hardcoded `confidence_score=0.98`, which is exactly what a
  fabricated number looks like. Causal precision — the fraction of proposed
  candidates that reproduce under forcing — is measured instead.
