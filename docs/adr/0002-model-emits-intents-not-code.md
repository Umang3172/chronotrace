# 2. The model emits typed intents, never source code

## Context

An agent that writes code to fix a flaky test can write `time.sleep(2)`. That
is not a hypothetical: it is the default behaviour of general coding assistants
on this task, because a sleep makes the test green and greenness is the visible
signal.

Anything the model emits has to be checkable. Source code is checkable only by
reading it, which is exactly the reviewer effort the tool exists to save.

## Decision

The model does exactly one thing: choose a repair pattern from a fixed set and
return a `RepairIntent` — a typed, schema-validated JSON object naming the
transformation, the shared scope, and the signal and wait sites. Deterministic
code applies it via LibCST. Diagnosis, patch application, policy enforcement and
verification contain no model calls.

## Consequences

- The space of possible patches is enumerable, so the policy gate can be
  complete rather than best-effort.
- The thing that decides is not the thing that verifies.
- Novel repairs outside the fixed transformation set are impossible. The system
  abstains instead, which is the intended trade.
- A malformed or hallucinated intent fails schema validation and is refused
  before it can touch a file.

## Alternatives considered

- **Model writes a diff, governor reviews it.** Rejected: the review surface
  becomes arbitrary Python, and "did this patch weaken the assertion" turns into
  an open-ended program-analysis problem instead of a closed one.
- **Model proposes, second model critiques.** Rejected: the critic's duties
  (primitive matching, scope checking, cycle detection) are all deterministic
  checks. An LLM performing them is a deterministic check with added variance.
