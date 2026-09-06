# 3. Forced replay instead of rerun-based verification

## Context

"We ran it 20 times and it passed" does not survive scrutiny. Gruber et al.
(ICST 2021) put the number of reruns needed for 95% confidence that a Python
test is *not* flaky at 170, and Alshammari et al. (ICSE 2021) found projects
where 10,000 reruns still missed known flaky tests. Rerun-based verification is
both expensive and weak.

The trace diff gives ChronoTrace something no rerun loop has: the identity of
the specific pair of operations whose order differs between passing and failing
runs. That converts verification from sampling into an experiment.

## Decision

Verification is tiered, and the tier reached is always reported:

| Tier | Method | Claim |
|---|---|---|
| 1 FORCED | harness gates reproduce the ordering | causality proven |
| 1b INFEASIBLE | the ordering times out | candidate unreachable |
| 2 PCT | seeded randomized scheduling | probabilistic bound |
| 3 STATISTICAL | plain reruns | residual flake check only |

Tier 1 requires **both** halves: the pre-patch run must fail under the forced
ordering and the post-patch run must pass under the identical ordering, with the
harness unchanged between them. One half alone proves nothing.

## Consequences

- A repair claim is an experiment with a control, not a sample.
- A Tier 2 or Tier 3 result is never described as proof. Silently degrading
  while still claiming causality is the one thing that would make the project
  dishonest, so the tier travels with the result everywhere it is displayed.
- Forced runs sweep consecutive seeds rather than repeating one, so that what is
  *not* being forced stays free. Freezing it would make a bug needing two
  constraints read as a single sufficient one.
- Tier 1 needs instrumented operations. Uninstrumented code degrades to Tier 3,
  reported as such.

## Alternatives considered

- **Reruns only, with a large N.** Rejected on cost and on strength: it cannot
  distinguish a repair from a timing change that merely makes the race rarer.
