# 1. Scope: Python asyncio only

## Context

Forced-interleaving replay is the load-bearing claim of the project: without it,
a diagnosis is a correlation and the verification story collapses back to
statistical reruns. Whether that claim survives depends entirely on whether an
ordering can actually be forced in the target runtime.

In CPython, OS threads cannot be arbitrarily scheduled from user space without
intercepting synchronization primitives or manipulating `sys.setswitchinterval`,
neither of which gives deterministic control. Multiprocessing is worse. asyncio
is different in kind: tasks run cooperatively on one thread and yield only at
`await` boundaries, and the loop chooses which ready callback runs next.

## Decision

The supported environment is Python asyncio. Threading and multiprocessing are
detected in order to **abstain**, never to repair.

## Consequences

- The forced scheduler is genuinely real rather than partly theatrical. Both
  orderings of a seeded race are reproducible on demand (see `tests/test_harness.py`).
- The wrong-primitive failure mode (P-5 in the source spec) largely dissolves:
  one paradigm means one primitive family, so an `asyncio.Event` injected for an
  asyncio race cannot silently do nothing.
- Coverage is narrower than "flaky test repair" in general. A threading race is
  a refusal with an explanation, which is the honest outcome, not a repair.
- Eight excellent asyncio races with a real deterministic scheduler are worth
  more than fifteen shallow ones across three paradigms.

## Alternatives considered

- **All three paradigms.** Rejected: the scheduler would be real for one of them
  and a rerun loop wearing its clothes for the other two, and the project's
  central claim would be false for most of its surface.
- **Threading via `sys.settrace`.** Rejected: enormous probe effect, and the
  perturbation would be larger than the timing differences being measured.
