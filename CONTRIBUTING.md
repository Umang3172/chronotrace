# Contributing

## Setup

```bash
uv sync --extra dev
uv run pre-commit install
```

`uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy chronotrace`
must exit clean. Not "mostly clean".

## The five things that are not negotiable

These are safety properties, not style preferences. A change that weakens one of
them will not be merged, however much it improves a number.

1. **The model never writes source code.** It emits a `RepairIntent`;
   deterministic code applies it. If a change requires the model to produce
   Python, it is the wrong change.
2. **The governor is complete, not best-effort.** Every rule in
   `chronotrace/govern/` is a safety check, and a rule that catches
   `time.sleep` but not an aliased import is a bypass, not a simpler rule. New
   rules need a matching entry in the adversarial gauntlet.
3. **Abstention paths stay.** `NOT_A_RACE`, `NO_INVERSION`, `NO_TRACE_PAIR` and
   the rest are required behaviours. "It always returns an answer" is the
   failure mode, not the goal.
4. **The verification tier reached is reported as measured.** Never describe a
   Tier 2 or Tier 3 result as proof of causality.
5. **No metric is hand-entered.** If `chronotrace eval` did not produce it, it
   does not go in the README.

## Fixing a flaky test in this repository

With a synchronization primitive, the way the product does. Never with a sleep,
a retry, or a longer timeout. The irony would be terminal.

## Adding a benchmark case

Each case is a directory under `benchmark/cases/` with the test, a
`ground_truth.json` recording the expected outcome, and a `README.md` explaining
the shape and the trap. Cases the system must *refuse* are as valuable as cases
it repairs — the false-repair rate is a headline metric.
