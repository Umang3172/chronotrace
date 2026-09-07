# Recorded model calls

Every model call made during an evaluation is recorded here, keyed by which call
it was — provider, arm, case, attempt — with both prompts, the raw response and
the token counts. This is what lets a reader reproduce a published number
offline, with no credentials and no GPU.

`three_arm/` holds the three-arm baseline recordings and, under
`three_arm/evidence/`, the captured traces and diagnoses each run reasoned
about. Replaying both is what makes a replay the same experiment rather than a
similar one.

## Fixtures written by the reference policy

The `provider` field names what produced a response. A value of
`reference-policy` means the response came from
`chronotrace/providers/reference_policy.py` — a hand-written decision
procedure, **not a model**. Such fixtures are test doubles. They demonstrate
that the deterministic layers work and say nothing about whether a model can
drive them, so they must never back a demo or a published result.

Seven such fixtures were deleted from this directory after one of them was found
to be powering the project's working demo.
