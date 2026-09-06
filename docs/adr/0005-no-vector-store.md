# 5. No vector store, no second agent

## Context

An early architecture included a vector store of past repairs with a small model
acting as a "memory matcher", and a node labelled as a multi-agent swarm that in
fact contained a single agent.

## Decision

Neither ships. The vector store is cut entirely. Agentic depth comes from
multi-step tool use inside one agent loop — request a trace slice, force a
candidate ordering, read the replay result, request source context, select a
pattern, request verification, decide — not from a second model.

## Consequences

- No retrieval infrastructure to run, seed or explain.
- The remaining agent loop is genuinely agentic: it takes actions, observes
  their results, and decides what to do next, including deciding to abstain.
- Authority stays deterministic. The loop can request a forced replay; it cannot
  decide that a rejected patch is acceptable.

## Alternatives considered

- **Add a critic agent.** Rejected: every duty proposed for it — primitive and
  paradigm matching, scope checking, deadlock detection — is a deterministic
  check that belongs in the governor. Moving them into a model would trade a
  decidable check for a probabilistic one and call it sophistication.
