# 6. Provider abstraction, local by default

## Context

The evaluation harness must not require a network. A reader who wants to check a
published number should be able to run one command and get it, and a demo that
depends on a live model call is a demo that can fail in front of an audience.

## Decision

Two protocols — `ModelProvider` and `TelemetrySink` — with local implementations
as the default and cloud implementations selected by a single environment
variable. `ReferencePolicyProvider` is a hand-written decision procedure used as
a test double; `OllamaProvider` and `BedrockProvider` call real models with a
schema that admits only a `RepairIntent`.

## Consequences

- The benchmark and eval harness run with no credentials. `repair --demo`
  deliberately does *not*: it refuses on the reference policy, because a demo
  driven by a hand-written policy would misrepresent what the system can do.
- Every provider call records its (request, response) pair, so a published
  result is replayable byte-for-byte and offline.
- **The reference policy is not a model and is never presented as one.** It
  reports no token counts, because a token count it invented would be a
  fabricated metric; the results table prints `n/a` and says why.
- Comparative arms A and B are *refused* on the local provider rather than run
  and caveated. A baseline drawn from this repository's own hand-written policy
  would describe this repository, not a model.
- Bedrock model ids are configuration with no default. Ids change between
  regions and releases, and a stale hardcoded id fails confusingly at runtime.

## Alternatives considered

- **Bedrock only.** Rejected: no offline evaluation, no reproducible demo, and
  every test in CI would need credentials.
