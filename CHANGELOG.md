# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-09-07

### Added

- **Forced-ordering harness** (`chronotrace/schedule/`) gating instrumented
  asyncio operations, with an INFEASIBLE result for orderings the code cannot
  produce, plus a deterministic event loop and a PCT priority scheduler.
- **Capture** — a pytest plugin emitting occurrence-indexed spans, execution
  fingerprints, and probe-effect measurement.
- **Diagnosis** — observed-order graph over three edge sources, backward slicing
  from the failed assertion, Ochiai ranking, confirmation by forcing, bug-depth
  reporting, and eight abstention paths.
- **Synthesis** — typed `RepairIntent` contract, LibCST cross-scope transformer,
  local reference provider with fixture recording, and a Bedrock provider.
- **Governor** — fifteen deterministic rules with an adversarial gauntlet of
  seventeen attack patches, runnable as `chronotrace gauntlet`.
- **Verification** — the tiered ladder with the tier reached always reported,
  measured overhead, and emission of a permanent forced-interleaving regression
  guard.
- **Benchmark** — fourteen seeded cases: nine asyncio races and five negative
  controls the system must refuse.
- **Eval harness** — three arms, producing every number the README claims.
- Next.js dashboard, ADRs, and CI.

### Known limitations

See the Limitations section of the README. They are load-bearing and are not to
be softened.
