# Deterministic-layer results — NOT a model result

> **Read this before quoting any number in this directory.**
>
> `results.json` here records `"provider": "local"`, which is what the
> **reference policy** was called before it was renamed `reference-policy`. The
> reference policy is a hand-written decision procedure, not a language model
> — see [the README](../../README.md#the-reference-policy-is-a-test-double).
>
> So the **100% repair rate in `results.md` is not a repair rate.** It is a
> hand-written policy scoring against the corpus it was written alongside, and
> it says nothing whatsoever about whether a model can make that decision. It
> is kept because it is still evidence of something real: capture, diagnosis,
> LibCST patching, the governor and forced replay work end to end across all
> fourteen cases without a model in the loop.

## Where the actual numbers live

| File | Provider | What it is |
|---|---|---|
| [`eval/results/FINDINGS.md`](../../eval/results/FINDINGS.md) | qwen2.5-coder:14b | **Canonical.** Every number the project README quotes. |
| `eval-results/` | qwen2.5-coder:14b | Working output of the last `chronotrace eval` run; the dashboard reads it. Four cases, Arm C only — a subset, not a result. |
| this directory | reference policy | Deterministic layers only. Not a model result. |

## Regenerating

The output of `uv run chronotrace eval --arm C --cases all`. Two things differ
between runs and both are expected:

- **Measured overhead** moves by a couple of tenths of a millisecond and can
  come out negative. It is a sub-millisecond quantity measured across process
  boundaries; read it as "too small to separate from noise at this sample size",
  which is why the README says exactly that rather than quoting it as a
  constant.
- **Natural flake rates** vary run to run, because the seeded races are genuinely
  nondeterministic. That is the point of them.

The categorical results — which cases the deterministic layers carry end to end,
which abstain and for what reason, and which verification tier each reaches —
have been stable across runs.
