# ChronoTrace — findings

Everything here was produced by `chronotrace three-arm` and `chronotrace eval`.
No figure is hand-entered. Local-model results throughout: **qwen2.5-coder:14b**
(14.8B, Q4_K_M, digest `9ec8897f747e…`) via Ollama 0.32.14, temperature 0.0,
seed 1729. A Bedrock run against a frontier model is planned; these are not
those numbers.

## The three arms

* **Arm A** — the model gets the test and the failure. No traces, no governor.
* **Arm B** — the same, plus the trace diff and ranked candidate inversions.
* **Arm C** — full ChronoTrace: typed intent, deterministic patching, policy
  gate, tiered verification.

Same model, temperature, seed, token cap, attempt budget and per-run timeout.
Capture and diagnosis run once per case and are shared by all three arms.
Verification is the same ladder with the same forced ordering for every arm.

## Results, split by race shape

R01–R06 are all one shape: a read-after-write on a shared resource. R14 is a
task-lifecycle race. **They are reported separately and deliberately not
averaged** — the difference between them is the finding, and a combined number
would hide it.

### R01–R06 — the shape the system was built for

| Metric | Arm A | Arm B | Arm C |
|---|---|---|---|
| Races repaired (verified) | 4 / 6 | 4 / 6 | **6 / 6** |
| **Band-aids injected** | **3 / 6** | **3 / 6** | **0 / 6** |
| CI seconds added per run | 0.02 s | 0.12 s | 0 s |

### R14 — the first case of a different shape

| Metric | Arm A | Arm B | Arm C |
|---|---|---|---|
| Repaired (verified) | **yes** | **yes** | **no** |
| Verification tier | `FORCED_UNREACHABLE` | `FORCED_UNREACHABLE` | `FAILED` |
| Band-aid | none | none | none |

**On the one case of a new shape, both unconstrained baselines got it right and
ChronoTrace got it wrong.** Arms A and B each wrote `await handle`, with a
comment saying why — *"Ensure the batch worker completes before the
assertion."* Arm C chose `INJECT_ASYNC_EVENT`, which is the wrong repair here,
and forced replay rejected it.

### Negative controls (all 5)

| Metric | Arm A | Arm B | Arm C |
|---|---|---|---|
| **False repairs** | **4 / 5** | **4 / 5** | **0 / 5** |
| Abstention accuracy | — | — | 5 / 5, correct reason |

### Cost

| | Arm A | Arm B | Arm C |
|---|---|---|---|
| Model calls | 12 | 12 | 9 |
| Total tokens | 9,075 | 10,788 | 18,364 |

Arm C costs roughly twice the tokens of a baseline. It sends the full diagnosis
as evidence, and it retries on an invalid intent.

## R12 — a perfect suspiciousness score, correctly refused

R12 brings up two replicas concurrently and asserts `primary or secondary`. The
top candidate scored **Ochiai 1.00** — present in every failing run and no
passing run, statistically indistinguishable from R01.

Forcing it failed **60%** of the time, not 100%. A rate strictly between 0 and 1
means the ordering is *necessary but not sufficient*: part of the cause, not the
whole of it. The second candidate forced at 40%. ChronoTrace reported
`DEPTH_GE_2_UNRESOLVED` and generated no patch.

Patching on the suspiciousness score would have synchronised one replica and
left the bug live, halving the failure rate. **On any rerun-based metric that
reads as an improvement.** Forcing is what separates the two.

## R14 — correct on the named shape, wrong on a new one

R14's worker publishes three items, each after its own round trip; the assertion
depends on all three. An event signalled by the write wakes the reader after the
*first* item, so it is checkably the wrong repair.

Arm C chose `INJECT_ASYNC_EVENT` and quoted the rule back:

> "The operations involve a read-after-write inversion over the same resource
> 'batch.items', with one operation writing and the other reading. The reader
> observed state the writer had not yet published…"

That describes R14 accurately at the surface. It is still the wrong repair,
because the assertion depends on the task *completing*, not on one write
landing. The model matched the shape rather than reasoning about what the
assertion depends on.

The intent retry loop did not help: across three attempts it re-chose
`INJECT_ASYNC_EVENT` every time. **Retries correct an under-specified intent;
they do not correct a misjudged one.**

## The comparison that matters

R14's flake rate in this run was **80%**. The patch ChronoTrace proposed and
then rejected reduced it to **9 failures in 20 runs — about 45%**.

A rerun-based verification gate would have accepted that patch. The test used to
fail most of the time and now fails less than half the time; every rerun-based
signal points at "improved". Datadog's attempt-to-fix flow retries 20 times;
BuildPulse confirms through PR checks. Neither can distinguish *fixed the race*
from *made it rarer*, because both look the same in a pass count.

Forced replay can. Pre-patch the ordering failed every time; post-patch it still
failed, so the patch did not defeat the interleaving and the tier is `FAILED`.
**This is the clearest evidence in the project for why the verification tier
matters**, and it happens to be evidence against our own system's judgement,
which is what makes it worth quoting.

## The abstention caveat

Arm C refused all five negative controls with the correct reason, in every run.
That number is weaker than it looks and should not be quoted without this
sentence:

**Four of the five controls are refused during diagnosis, before the model is
consulted at all.** `NOT_A_RACE` (N01, N02) and `NO_TRACE_PAIR` (N03, N06) are
reached by deterministic code; the model is never asked. N07 is refused by
paradigm detection, also before any model call.

So 5/5 demonstrates that the **deterministic refusal paths work**. It
demonstrates nothing about whether a model would decline when asked. No control
in the corpus reaches the model, so the corpus cannot answer that question.

## The generalization limit

Stated so it survives being asked hostilely:

> Six of our seven repairable cases are read-after-write races on a shared
> resource. The intent prompt names that condition explicitly. On those six, the
> model chooses correctly six times out of six. On the one case we added of a
> different shape, it chose wrong — and the unconstrained baselines, which were
> given no rule to follow, chose right. We have evidence that the system works
> on the shape it was told about. We do not have evidence that it generalizes,
> and the one experiment we ran on that question came back negative.

The honest scope of the claim:

* **Constraint prevents harm.** 0 band-aids against 3/6, and 0/5 false repairs
  against 4/5, in every run and on both models tested. This is the strongest and
  most reproducible result in the project.
* **Verification catches wrong repairs**, including our own. R14 is the proof.
* **Constraint does not confer judgement.** The model still has to pick the
  right pattern, and on a shape the prompt does not name, it did not.

## Known limitations

1. **Seeded benchmark**, 7 repairable cases and 5 controls, written for this
   project. Directional, not a population estimate.
2. **One race shape dominates.** Six of seven repairable cases share the shape
   the prompt names. R14 is a single counter-example, not a survey.
3. **Local models only.** Both are quantised. Bedrock is untested.
4. **Controls never reach the model**, so abstention accuracy measures
   deterministic refusal only.
5. **asyncio only.** Threading and multiprocessing are detected in order to
   refuse them.
6. **The reference policy is a test double**, not a model, and the demo refuses
   to run on it.
